import time
from typing import Optional

from app.core.config import settings
from app.retrieval.index_store import search
from app.db.queries import fetch_chunks_by_faiss_ids


def _dedupe_keep_best_score(rows: list[dict]) -> list[dict]:
    """
    Dedupe by (source,page) keeping the row with highest _score.
    """
    best: dict[tuple, dict] = {}
    for r in rows:
        key = (r.get("source"), r.get("page"))
        cur = best.get(key)
        if cur is None:
            best[key] = r
            continue
        # keep higher score
        if (r.get("_score") is not None) and (cur.get("_score") is None or r["_score"] > cur["_score"]):
            best[key] = r
    return list(best.values())


def run_retrieval(query: str) -> tuple[list[dict], Optional[dict], float]:
    """
    Returns: (rows, debug, latency_ms)
    rows: list of dicts with at least {source, page, chunk_id, text, _score}
    """
    t0 = time.perf_counter()

    t_search0 = time.perf_counter()
    faiss_ids, scores = search(query, settings.search_candidates_k)
    top1 = scores[0] if scores else None
    top2 = scores[1] if scores and len(scores) > 1 else None
    gap = (top1 - top2) if (top1 is not None and top2 is not None) else None
    t_search1 = time.perf_counter()

    # --- Abstention rule (robust no-evidence) ---
    min_top = settings.min_top_score
    min_gap = settings.min_score_gap  # nuevo setting

    should_abstain = (not faiss_ids)

    # If we have scores, apply thresholds
    if not should_abstain and top1 is not None:
        margin = settings.min_top_score_margin
        # 1) low top score
        if min_top is not None and top1 < min_top:
            should_abstain = True
            abstain_reason = "no_evidence_or_low_top_score"
        # 2) low separation between top1 and top2 (flat ranking)
        elif (gap is not None and min_gap is not None and margin is not None
            and top1 < (min_top + margin) and gap < min_gap):
            should_abstain = True
            abstain_reason = "no_evidence_low_score_gap_near_threshold"
        else:
            abstain_reason = None
    else:
        abstain_reason = "no_evidence_empty_search"

    if should_abstain:
        latency_ms = (time.perf_counter() - t0) * 1000
        dbg = None
        if settings.debug_rag:
            dbg = {
                "model": settings.embedding_model_name,
                "index_dir": settings.index_dir,
                "search_candidates_k": settings.search_candidates_k,
                "max_citations": settings.max_citations,
                "min_top_score": settings.min_top_score,
                "min_row_score": settings.min_row_score,
                "min_score_gap": settings.min_score_gap,
                "faiss_ids": faiss_ids,
                "scores": scores,
                "top1": top1,
                "top2": top2,
                "gap": gap,
                "timings_ms": {
                    "search_total": (t_search1 - t_search0) * 1000,
                    "total": latency_ms,
                },
                "reason": abstain_reason,
            }
        return [], dbg, latency_ms

    # Build score lookup by faiss_id (IMPORTANT: don't assume DB returns same order)
    score_by_id = {}
    if scores:
        for _id, _s in zip(faiss_ids, scores):
            score_by_id[int(_id)] = float(_s)

    t_db0 = time.perf_counter()
    rows = fetch_chunks_by_faiss_ids(faiss_ids, settings.embedding_model_name)
    t_db1 = time.perf_counter()

    paired: list[dict] = []
    for row in rows:
        r = dict(row)

        # Try to read the id used in your DB table for mapping scores
        # Preferred: "faiss_id" (recommend you include it in the SELECT)
        rid = r.get("faiss_id", None)
        if rid is None:
            # fallback: sometimes it's called "id"
            rid = r.get("id", None)

        if rid is not None:
            try:
                rid_int = int(rid)
            except Exception:
                rid_int = None
        else:
            rid_int = None

        r["_score"] = score_by_id.get(rid_int) if rid_int is not None else None
        paired.append(r)

    # Sort by score desc (None last)
    paired.sort(key=lambda x: (x.get("_score") is not None, x.get("_score") or -1e9), reverse=True)

    # Optional: filter out weak rows as well (not just top_score)
    min_row = settings.min_row_score
    if min_row is not None:
        paired = [r for r in paired if (r.get("_score") is not None and r["_score"] >= min_row)]

    # Dedupe by (source,page), keep best score
    paired = _dedupe_keep_best_score(paired)

    # Sort again after dedupe
    paired.sort(key=lambda x: (x.get("_score") is not None, x.get("_score") or -1e9), reverse=True)

    # Apply max citations
    paired = paired[: settings.max_citations]

    latency_ms = (time.perf_counter() - t0) * 1000

    # If after filtering we have nothing => abstain
    if not paired:
        dbg = None
        if settings.debug_rag:
            dbg = {
                "model": settings.embedding_model_name,
                "index_dir": settings.index_dir,
                "search_candidates_k": settings.search_candidates_k,
                "max_citations": settings.max_citations,
                "min_top_score": settings.min_top_score,
                "min_row_score": settings.min_row_score,
                "faiss_ids": faiss_ids,
                "scores": scores,
                "timings_ms": {
                    "search_total": (t_search1 - t_search0) * 1000,
                    "db_fetch": (t_db1 - t_db0) * 1000,
                    "total": latency_ms,
                },
                "reason": "all_candidates_filtered_by_min_row_score",
            }
        return [], dbg, latency_ms

    dbg = None
    if settings.debug_rag:
        dbg = {
            "model": settings.embedding_model_name,
            "index_dir": settings.index_dir,
            "search_candidates_k": settings.search_candidates_k,
            "max_citations": settings.max_citations,
            "min_top_score": settings.min_top_score,
            "min_row_score": settings.min_row_score,
            "faiss_ids": faiss_ids,
            "scores": scores,
            "returned_chunks": [
                {
                    "chunk_id": r.get("chunk_id"),
                    "faiss_id": r.get("faiss_id", r.get("id")),
                    "source": r.get("source"),
                    "page": r.get("page"),
                    "_score": r.get("_score"),
                }
                for r in paired
            ],
            "timings_ms": {
                "search_total": (t_search1 - t_search0) * 1000,
                "db_fetch": (t_db1 - t_db0) * 1000,
                "total": latency_ms,
            },
        }

    return paired, dbg, latency_ms
