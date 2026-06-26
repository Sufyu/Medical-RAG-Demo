# Main FastAPI application entry point - will be populated with API endpoints
from fastapi import FastAPI
from app.models import QueryRequest, QueryResponse
from app.retrieval import retrieval

app = FastAPI()

#@app.get("/")
#def read_root():
#    return {"message": "Hello world"}

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    return QueryResponse(
        question=request.question,
        answer=f"Received your question: {request.question}",
        chunks=retrieval(request.question, request.top_k),
        latency_ms=0.0
    )

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}