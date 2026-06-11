from pydantic import BaseModel, Field
from typing import List


class QueryRequest(BaseModel):
    """
    Request model for incoming user queries.
    
    Attributes:
        question: The medical question to ask (3-500 characters)
        top_k: Number of document chunks to retrieve (1-10, default 4)
    """
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)


class RetrievedChunk(BaseModel):
    """
    Represents a single retrieved document chunk from the knowledge base.
    
    Attributes:
        text: The actual text content of the document chunk
        source: Where the chunk came from (document name, URL, etc.)
        score: Relevance score (0-1), higher = more relevant to the query
    """
    text: str
    source: str
    score: float


class QueryResponse(BaseModel):
    """
    Final response returned to the user.
    
    Attributes:
        question: Echo back the original question
        answer: The LLM-generated answer based on retrieved chunks
        chunks: List of retrieved document chunks with scores
        latency_ms: Response time in milliseconds (for monitoring)
    """
    question: str
    answer: str
    chunks: List[RetrievedChunk]
    latency_ms: int
