#!/usr/bin/env python3
"""Test script to run the retrieve function in isolation."""

import os
from .retrieval import retrieve

if __name__ == "__main__":
    # Test question
    question = "What are the symptoms of diabetes?"
    
    print(f"Querying: {question}\n")
    print("=" * 60)
    
    # Retrieve chunks
    chunks = retrieve(question, top_k=5)
    
    # Display results
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Score: {chunk.score:.4f}")
        print(f"Source: {chunk.source}")
        print(f"Text: {chunk.text[:200]}..." if len(chunk.text) > 200 else f"Text: {chunk.text}")
    
    print(f"\n{'=' * 60}")
    print(f"Retrieved {len(chunks)} chunks")
