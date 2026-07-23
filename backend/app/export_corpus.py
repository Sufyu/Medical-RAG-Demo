import json
import os
from sqlalchemy import create_engine, text
import numpy as np

def export_corpus(corpus_dir: str = "../docs"):
    """Export chunks and embeddings from database to corpus.json."""
    engine = create_engine(os.environ["DATABASE_URL"])
    
    with engine.connect() as cx:
        # Query all chunks with embeddings
        rows = cx.execute(text("""
            SELECT text, source, embedding
            FROM chunks
        """)).fetchall()
    
    # Prepare data for JSON export
    chunks = []
    embeddings = []
    
    for row in rows:
        chunk_text, source, embedding_str = row
        chunks.append({"text": chunk_text, "source": source})
        # Parse the embedding string back to list
        embedding = eval(embedding_str)  # Convert string representation back to list
        embeddings.append(embedding)
    
    # Save to corpus.json in docs directory
    corpus_path = os.path.join(os.path.dirname(__file__), "../docs", "corpus.json")
    with open(corpus_path, "w") as f:
        json.dump({
            "chunks": chunks,
            "embeddings": embeddings
        }, f)
    
    print(f"Exported {len(chunks)} chunks to {corpus_path}")
    print(f"Corpus size: {sum(len(c['text']) for c in chunks)} characters")

if __name__ == "__main__":
    export_corpus()
