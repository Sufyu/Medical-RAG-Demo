# Main FastAPI application entry point - will be populated with API endpoints
from fastapi import FastAPI
from app.models import QueryRequest, QueryResponse
from app.retrieval import retrieve
from mangum import Mangum

app = FastAPI()

#@app.get("/")
#def read_root():
#    return {"message": "Hello world"}

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    return QueryResponse(
        question=request.question,
        answer=f"Received your question: {request.question}",
        chunks=retrieve(request.question, request.top_k),
        latency_ms=0.0
    )

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

# Lambda handler
handler = Mangum(app, lifespan="off")