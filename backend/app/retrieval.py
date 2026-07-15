import os
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import anthropic
from .models import RetrievedChunk

MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
DIM = 384
_engine = create_engine(os.environ["DATABASE_URL"])
_llm = anthropic.Client(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def retrieve(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    q_emb = MODEL.encode([question], normalize_embeddings=True)[0].tolist()
    with _engine.connect() as cx:
        rows = cx.execute(text("""
          SELECT text, source, 1 - (embedding <=> :q) AS score
          FROM chunks ORDER BY embedding <=> :q LIMIT :k
        """), {"q": str(q_emb), "k": top_k}).fetchall()
    return [RetrievedChunk(text=r[0], source=r[1], score=float(r[2])) for r in rows]


def answer(question: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "I don't have any context to answer that question."
    context = "\n\n---\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    prompt = f"""Answer the question using only the context. If the context is insufficient, say so.

Context:
{context}

Question: {question}"""
    resp = _llm.completions.create(
        model="claude-haiku-4-5-20251001",
        max_tokens_to_sample=500,
        prompt=prompt,
    )
    # Anthropic returns text in resp.completion
    return getattr(resp, "completion", str(resp))