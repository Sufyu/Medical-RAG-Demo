import os, glob
from typing import List

from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None
 
MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
DIM = 384  # MiniLM-L6 output dim
 
def chunk(txt: str, size: int = 400, overlap: int = 50) -> list[str]:
    words = txt.split()
    out = []
    for i in range(0, len(words), size - overlap):
        out.append(" ".join(words[i:i + size]))
    return out
 

def read_pdf_text(path: str) -> str:
    """
    Extract text from a PDF file using pypdf (if available).

    Raises a RuntimeError with an installation hint if pypdf is not installed.
    """
    if PdfReader is None:
        raise RuntimeError(
            "pypdf is not installed. Install it with `pip install pypdf` to read PDFs.`"
        )
    reader = PdfReader(path)
    pages: List[str] = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n\n".join(pages)
 
def main(corpus_dir: str = "../docs"):
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as cx:
        cx.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        cx.execute(text(f"""
          CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding vector({DIM}) NOT NULL
          )"""))
        cx.execute(text("CREATE INDEX IF NOT EXISTS chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"))
        cx.execute(text("TRUNCATE chunks"))

    # discover supported files (md, txt, pdf)
    docs: List[str] = []
    docs.extend(glob.glob(f"{corpus_dir}/*.md"))
    docs.extend(glob.glob(f"{corpus_dir}/*.txt"))
    docs.extend(glob.glob(f"{corpus_dir}/*.pdf"))

    for path in docs:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            raw = read_pdf_text(path)
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        pieces = chunk(raw)
        embs = MODEL.encode(pieces, normalize_embeddings=True).tolist()
        with engine.begin() as cx:
            for piece, emb in zip(pieces, embs):
                cx.execute(
                  text("INSERT INTO chunks(source, text, embedding) VALUES (:s, :t, :e)"),
                  {"s": path, "t": piece, "e": str(emb)},
                )
    print("Ingested", len(docs), "docs")
 
if __name__ == "__main__":
    main()
