# Main FastAPI application entry point - will be populated with API endpoints
from fastapi import FastAPI
from app.models import QueryRequest, QueryResponse, ConversationRequest, ConversationResponse, ConversationTurn
# from app.retrieval import retrieve
from app.retrieval_lambda import retrieve
from app.retrieval_lambda import answer
from mangum import Mangum
import boto3
import anthropic
import time
import os
import uuid
from typing import List
from app.logging_setup import init
import logging

# Initialize logging
init()
logger = logging.getLogger("app")

# Initialize the FastAPI app
app = FastAPI()

@app.middleware("http")
async def log_requests(request, call_next):
    request_id = str(uuid.uuid4())
    start = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start) * 1000
    logger.info(
        "request completed",
        extra={"request_id": request_id, "latency_ms": round(latency_ms, 2)}
    )
    response.headers["X-Request-ID"] = request_id
    return response

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
conversation_table = dynamodb.Table('conversation-history')
_llm = anthropic.Anthropic()

#@app.get("/")
#def read_root():
#    return {"message": "Hello world"}

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    chunk_resp = retrieve(request.question, request.top_k)
    return QueryResponse(
        question=request.question,
        answer=answer(request.question, chunk_resp),
        chunks=chunk_resp,
        latency_ms=0.0
    )

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/conversation", response_model=ConversationResponse)
async def handle_conversation(request: ConversationRequest):
    """
    Multi-turn conversation endpoint with DynamoDB persistence.
    
    Retrieves last 5 turns of conversation history, injects into prompt,
    generates answer using Claude, stores new turn, and returns updated history.
    """
    # Retrieve last 5 turns from DynamoDB
    if request.conversation_id:
        try:
            response = conversation_table.query(
                KeyConditionExpression='conversation_id = :cid',
                ExpressionAttributeValues={':cid': request.conversation_id},
                ScanIndexForward=False,  # Descending by timestamp (newest first)
                Limit=5
            )
            history_items = response.get('Items', [])
        except Exception as e:
            # Table might not exist or other error - start fresh
            history_items = []
    else:
        history_items = []
    
    # Convert to list of ConversationTurn (reverse to get chronological order)
    history: List[ConversationTurn] = [
        ConversationTurn(question=item['question'], answer=item['answer'])
        for item in reversed(history_items)
    ]
    
    # Build conversation history string for prompt
    history_str = ""
    if history:
        history_str = "\n\n".join(
            f"Q: {turn.question}\nA: {turn.answer}" for turn in history
        )
        history_str = f"\n\nPrevious conversation:\n{history_str}\n\n"
    
    # Retrieve relevant chunks for context (include history in retrieval query)
    retrieval_query = f"{history_str}\nCurrent question: {request.question}"
    chunks = retrieve(retrieval_query, top_k=4)
    context = "\n\n---\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    
    # Build prompt with history and context
    prompt = f"""Answer the question using the conversation history and the context below. If both are insufficient, say so.{history_str}
Context:
{context}

Question: {request.question}"""
    
    # Generate answer with Claude
    resp = _llm.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    answer_text = resp.content[0].text
    
    # Store new turn in DynamoDB
    timestamp = int(time.time() * 1000)
    expires_at = timestamp + (2 * 24 * 60 * 60)  # 2 days
    if(request.conversation_id):
        put_conversation_id = request.conversation_id
    else:
        put_conversation_id = str(uuid.uuid4())

    try:
        conversation_table.put_item(
            Item={
                'conversation_id': put_conversation_id,
                'timestamp': timestamp,
                'question': request.question,
                'answer': answer_text,
                'expires_at': expires_at
            }
        )
    except Exception as e:
        # Log error but don't fail the request
        logger.error("Failed to store conversation", extra={"error": str(e)})
    
    # Return response with updated history
    updated_history = history + [ConversationTurn(question=request.question, answer=answer_text)]
    
    return ConversationResponse(
        conversation_id=put_conversation_id,
        answer=answer_text,
        history=updated_history
    )


# Lambda handler
handler = Mangum(app, lifespan="off")