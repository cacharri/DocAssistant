import time
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Request
from typing import Optional

from app.core.config import settings
from app.retrieval.index_store import search
from app.db.queries import fetch_chunks_by_faiss_ids

router = APIRouter()
logger = logging.getLogger("app.ask")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

class AskResponse(BaseModel):
    answer: str
    citations: list[dict] = []
    request_id: str
    latency_ms: float
    cost_usd: float
    debug: Optional[dict] = None


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, request: Request):
    request_id = getattr(request.state, "request_id", "-")
    t0 = time.perf_counter()

    logger.info(
        "ask_received input_chars=%d",
        len(payload.question),
        extra={"request_id": request_id},
    )

        # Phase 1: vector search (includes model/index lazy-load)
    t_search0 = time.perf_counter()
    faiss_ids, scores = search(payload.question, settings.top_k)
    t_search1 = time.perf_counter()

    # Phase 2: threshold -> "no sé"
    if not faiss_ids or (scores and max(scores) < settings.min_score):
        latency_ms = (time.perf_counter() - t0) * 1000
        dbg = None
        if settings.debug_rag:
            dbg = {
                "model": settings.embedding_model_name,
                "index_dir": settings.index_dir,
                "top_k": settings.top_k,
                "min_score": settings.min_score,
                "faiss_ids": faiss_ids,
                "scores": scores,
                "timings_ms": {
                    "search_total": (t_search1 - t_search0) * 1000,
                    "total": latency_ms,
                },
                "reason": "no_evidence_or_low_score",
            }
        return AskResponse(
            answer="No tengo evidencia suficiente en los documentos para responder con seguridad.",
            citations=[],
            request_id=request_id,
            latency_ms=latency_ms,
            cost_usd=0.0,
            debug=dbg,
        )

    # Phase 3: DB fetch
    t_db0 = time.perf_counter()
    rows = fetch_chunks_by_faiss_ids(faiss_ids, settings.embedding_model_name)
    t_db1 = time.perf_counter()

    citations = []
    excerpts = []
    for i, row in enumerate(rows):
        citations.append(
            {
                "source": row["source"],
                "page": row["page"],
                "chunk_id": row["chunk_id"],
                "score": scores[i] if i < len(scores) else None,
            }
        )
        excerpts.append(f"- {row['text'][:350]}")

    answer = (
        "He encontrado estos fragmentos relevantes en tus documentos. "
        "Revisa las citas para verificar:\n\n" + "\n".join(excerpts)
    )

    latency_ms = (time.perf_counter() - t0) * 1000

    dbg = None
    if settings.debug_rag:
        dbg = {
            "model": settings.embedding_model_name,
            "index_dir": settings.index_dir,
            "top_k": settings.top_k,
            "min_score": settings.min_score,
            "faiss_ids": faiss_ids,
            "scores": scores,
            "returned_chunks": [
                {"chunk_id": c["chunk_id"], "source": c["source"], "page": c["page"]}
                for c in citations
            ],
            "timings_ms": {
                "search_total": (t_search1 - t_search0) * 1000,
                "db_fetch": (t_db1 - t_db0) * 1000,
                "total": latency_ms,
            },
        }

    return AskResponse(
        answer=answer,
        citations=citations,
        request_id=request_id,
        latency_ms=latency_ms,
        cost_usd=0.0,
        debug=dbg,
    )
