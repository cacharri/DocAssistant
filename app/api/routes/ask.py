import time
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Request
from typing import Optional
from app.retrieval.retrieve import run_retrieval
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

