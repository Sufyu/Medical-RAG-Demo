import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import anthropic
from .models import RetrievedChunk

MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
_index = None
_chunks = None
_llm = anthropic.Anthropic()

def _load():
    """Load the corpus and build FAISS index (lazy loading on first use)."""
    global _index, _chunks
    if _index is not None:
        return
    
    # Load the corpus JSON file
    corpus_path = os.path.join(os.path.dirname(__file__), "corpus.json")
    with open(corpus_path) as f:
        data = json.load(f)
    
    _chunks = data["chunks"]
    embs = np.array(data["embeddings"], dtype="float32")
    
    # Create FAISS index for inner product (cosine similarity with normalized vectors)
    _index = faiss.IndexFlatIP(embs.shape[1])
    _index.add(embs)

def retrieve(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Retrieve relevant chunks using FAISS similarity search."""
    _load()
    
    # Encode query and normalize
    q = MODEL.encode([question], normalize_embeddings=True).astype("float32")
    
    # Search for top_k similar vectors
    scores, idx = _index.search(q, top_k)
    
    # Return retrieved chunks with scores
    return [
        RetrievedChunk(
            text=_chunks[i]["text"],
            source=_chunks[i]["source"],
            score=float(s)
        )
        for s, i in zip(scores[0], idx[0])
    ]

def answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Generate answer using Anthropic API with retrieved context."""
    if not chunks:
        return "I don't have any context to answer that question."
    
    context = "\n\n---\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    prompt = f"""Answer the question using only the context. If the context is insufficient, say so.

Context:
{context}

Question: {question}"""
    
    resp = _llm.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return resp.content[0].text
