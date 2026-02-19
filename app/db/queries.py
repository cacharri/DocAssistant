from typing import List, Dict, Any, Optional
from app.db.conn import get_conn

def fetch_all_chunks() -> List[Dict[str, Any]]:
    # We join documents to keep source for citations later
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  c.id as chunk_id,
                  c.text as text,
                  c.page as page,
                  d.source as source
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.id ASC
                """
            )
            rows = cur.fetchall()
    out = []
    for chunk_id, text, page, source in rows:
        out.append({"chunk_id": chunk_id, "text": text, "page": page, "source": source})
    return out

def upsert_chunk_embedding(chunk_id: int, model_name: str, dim: int, faiss_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunk_embeddings (chunk_id, model_name, dim, faiss_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO UPDATE
                SET model_name=EXCLUDED.model_name, dim=EXCLUDED.dim, faiss_id=EXCLUDED.faiss_id
                """,
                (chunk_id, model_name, dim, faiss_id),
            )

def fetch_chunks_by_faiss_ids(faiss_ids: List[int], model_name: str) -> List[Dict[str, Any]]:
    # keep order of faiss_ids
    if not faiss_ids:
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  e.faiss_id,
                  c.id as chunk_id,
                  c.text,
                  c.page,
                  d.source
                FROM chunk_embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE e.model_name = %s AND e.faiss_id = ANY(%s)
                """,
                (model_name, faiss_ids),
            )
            rows = cur.fetchall()

    by_faiss = {}
    for faiss_id, chunk_id, text, page, source in rows:
        by_faiss[int(faiss_id)] = {"chunk_id": chunk_id, "text": text, "page": page, "source": source}

    return [by_faiss[fid] for fid in faiss_ids if fid in by_faiss]
