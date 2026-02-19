from typing import Optional
from app.db.conn import get_conn

def upsert_document(source: str, doc_type: str, sha256: str, bytes_size: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (source, doc_type, sha256, bytes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source, sha256) DO UPDATE SET bytes = EXCLUDED.bytes
                RETURNING id
                """,
                (source, doc_type, sha256, bytes_size),
            )
            return cur.fetchone()[0]

def chunk_exists(document_id: int, chunk_index: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM chunks WHERE document_id=%s AND chunk_index=%s LIMIT 1",
                (document_id, chunk_index),
            )
            return cur.fetchone() is not None

def insert_chunk(document_id: int, chunk_index: int, page: Optional[int], char_start: int, char_end: int, text: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, page, char_start, char_end, text)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, chunk_index) DO NOTHING
                """,
                (document_id, chunk_index, page, char_start, char_end, text),
            )
