import os
import json
import threading
from dataclasses import dataclass
import faiss
import numpy as np
from app.core.config import settings
from app.retrieval.embeddings import Embedder

@dataclass
class IndexBundle:
    embedder: Embedder
    index: faiss.Index
    meta: dict

_lock = threading.Lock()
_bundle: IndexBundle | None = None

def _paths():
    base = settings.index_dir
    return {
        "dir": base,
        "faiss": os.path.join(base, "index.faiss"),
        "meta": os.path.join(base, "meta.json"),
    }

def load_index_bundle() -> IndexBundle:
    global _bundle
    if _bundle is not None:
        return _bundle

    with _lock:
        if _bundle is not None:
            return _bundle

        p = _paths()
        if not os.path.exists(p["faiss"]) or not os.path.exists(p["meta"]):
            raise RuntimeError(f"Index not found. Build it first. Missing {p['faiss']} or {p['meta']}")

        with open(p["meta"], "r", encoding="utf-8") as f:
            meta = json.load(f)

        index = faiss.read_index(p["faiss"])
        embedder = Embedder(settings.embedding_model_name)

        _bundle = IndexBundle(embedder=embedder, index=index, meta=meta)
        return _bundle

def search(query: str, top_k: int) -> tuple[list[int], list[float]]:
    b = load_index_bundle()
    q = b.embedder.encode([query])  # [1, dim]
    D, I = b.index.search(q, top_k)  # cosine sim if using IndexFlatIP + normalized
    ids = [int(x) for x in I[0].tolist() if int(x) != -1]
    scores = [float(x) for x in D[0].tolist()[:len(ids)]]
    return ids, scores
