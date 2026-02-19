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

def _clean_excerpt(text: str, max_chars: int = 420) -> str:
    # colapsa whitespace (newlines, tabs, múltiple espacios)
    t = " ".join((text or "").split())
    if len(t) > max_chars:
        t = t[:max_chars].rstrip() + "…"
    return t


def _dedupe_by_source_page(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = (r.get("source"), r.get("page"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def _run_retrieval(query: str):
    t0 = time.perf_counter()

    t_search0 = time.perf_counter()
    faiss_ids, scores = search(query, settings.search_candidates_k)
    t_search1 = time.perf_counter()

    if not faiss_ids or (scores and max(scores) < settings.min_score):
        latency_ms = (time.perf_counter() - t0) * 1000
        dbg = None
        if settings.debug_rag:
            dbg = {
                "model": settings.embedding_model_name,
                "index_dir": settings.index_dir,
                "search_candidates_k": settings.search_candidates_k,
                "max_citations": settings.max_citations,
                "min_score": settings.min_score,
                "faiss_ids": faiss_ids,
                "scores": scores,
                "timings_ms": {
                    "search_total": (t_search1 - t_search0) * 1000,
                    "total": latency_ms,
                },
                "reason": "no_evidence_or_low_score",
            }
        return [], dbg, latency_ms, faiss_ids, scores, (t_search1 - t_search0) * 1000, 0.0

    t_db0 = time.perf_counter()
    rows = fetch_chunks_by_faiss_ids(faiss_ids, settings.embedding_model_name)
    t_db1 = time.perf_counter()

    paired = []
    for i, row in enumerate(rows):
        r = dict(row)
        r["_score"] = scores[i] if i < len(scores) else None
        paired.append(r)

    paired = _dedupe_by_source_page(paired)
    paired = paired[: settings.max_citations]

    latency_ms = (time.perf_counter() - t0) * 1000

    dbg = None
    if settings.debug_rag:
        dbg = {
            "model": settings.embedding_model_name,
            "index_dir": settings.index_dir,
            "search_candidates_k": settings.search_candidates_k,
            "max_citations": settings.max_citations,
            "min_score": settings.min_score,
            "faiss_ids": faiss_ids,
            "scores": scores,
            "returned_chunks": [
                {"chunk_id": r.get("chunk_id"), "source": r.get("source"), "page": r.get("page")}
                for r in paired
            ],
            "timings_ms": {
                "search_total": (t_search1 - t_search0) * 1000,
                "db_fetch": (t_db1 - t_db0) * 1000,
                "total": latency_ms,
            },
        }

    return paired, dbg, latency_ms, faiss_ids, scores, (t_search1 - t_search0) * 1000, (t_db1 - t_db0) * 1000

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

class AskResponse(BaseModel):
    answer: str
    citations: list[dict] = []
    request_id: str
    latency_ms: float
    cost_usd: float
    debug: Optional[dict] = None

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)

class SearchHit(BaseModel):
    source: str
    page: int
    chunk_id: int
    score: Optional[float] = None
    text: str

class SearchResponse(BaseModel):
    hits: list[SearchHit]
    request_id: str
    latency_ms: float
    debug: Optional[dict] = None

@router.post("/search", response_model=SearchResponse)
def search_endpoint(payload: SearchRequest, request: Request):
    request_id = getattr(request.state, "request_id", "-")

    rows, dbg, latency_ms, *_ = _run_retrieval(payload.query)

    hits = []
    for r in rows:
        hits.append(
            SearchHit(
                source=r.get("source"),
                page=r.get("page"),
                chunk_id=r.get("chunk_id"),
                score=r.get("_score"),
                text=_clean_excerpt(r.get("text", ""), max_chars=1200),
            )
        )

    return SearchResponse(
        hits=hits,
        request_id=request_id,
        latency_ms=latency_ms,
        debug=dbg,
    )
@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, request: Request):
    request_id = getattr(request.state, "request_id", "-")

    logger.info(
        "ask_received input_chars=%d",
        len(payload.question),
        extra={"request_id": request_id},
    )

    rows, dbg, latency_ms, *_ = _run_retrieval(payload.question)

    if not rows:
        return AskResponse(
            answer="No tengo evidencia suficiente en los documentos para responder con seguridad.",
            citations=[],
            request_id=request_id,
            latency_ms=latency_ms,
            cost_usd=0.0,
            debug=dbg,
        )

    citations = []
    excerpts = []
    for r in rows:
        citations.append(
            {
                "source": r.get("source"),
                "page": r.get("page"),
                "chunk_id": r.get("chunk_id"),
                "score": r.get("_score"),
            }
        )
        excerpts.append(f"- {_clean_excerpt(r.get('text', ''))}")

    answer = (
        "He encontrado estos fragmentos relevantes en tus documentos. "
        "Revisa las citas para verificar:\n\n" + "\n".join(excerpts)
    )

    return AskResponse(
        answer=answer,
        citations=citations,
        request_id=request_id,
        latency_ms=latency_ms,
        cost_usd=0.0,
        debug=dbg,
    )

