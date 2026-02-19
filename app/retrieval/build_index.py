import os
import json
from pathlib import Path
import faiss
import numpy as np

from app.core.config import settings
from app.db.queries import fetch_all_chunks, upsert_chunk_embedding
from app.retrieval.embeddings import Embedder

def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

def main():
    chunks = fetch_all_chunks()
    if not chunks:
        raise SystemExit("No chunks found in DB. Run ingestion first.")

    texts = [c["text"] for c in chunks]
    chunk_ids = [int(c["chunk_id"]) for c in chunks]

    embedder = Embedder(settings.embedding_model_name)
    embs = embedder.encode(texts)  # [n, dim], normalized

    n, dim = embs.shape

    # Use inner product on normalized vectors => cosine similarity
    index = faiss.IndexFlatIP(dim)
    index.add(embs)

    ensure_dir(settings.index_dir)
    faiss_path = os.path.join(settings.index_dir, "index.faiss")
    meta_path = os.path.join(settings.index_dir, "meta.json")

    faiss.write_index(index, faiss_path)

    meta = {
        "model_name": settings.embedding_model_name,
        "dim": dim,
        "num_vectors": n,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # Persist mapping chunk_id -> faiss_id (faiss_id is the vector position)
    for faiss_id, chunk_id in enumerate(chunk_ids):
        upsert_chunk_embedding(chunk_id=chunk_id, model_name=settings.embedding_model_name, dim=dim, faiss_id=faiss_id)

    print(f"Built FAISS index: {faiss_path}")
    print(f"Vectors: {n}, dim: {dim}")

if __name__ == "__main__":
    main()
