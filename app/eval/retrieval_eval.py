import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

from app.retrieval.retrieve import run_retrieval


def _basename(p: str) -> str:
    return os.path.basename(p or "")


def _norm_source(s: str) -> str:
    # normalize for robust matching
    return _basename(s).strip().lower()


def _safe_int(x: Any, default: int = -1) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _load_jsonl(path: str) -> list[dict]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


@dataclass
class GoldMetrics:
    n_gold: int = 0
    recall_hits: int = 0
    mrr_sum: float = 0.0


@dataclass
class NoEvidenceMetrics:
    n_no_evidence: int = 0
    no_evidence_correct: int = 0  # predicted empty when expected empty
    false_evidence: int = 0       # predicted non-empty when expected empty


def _case_has_gold(case: dict) -> bool:
    exp = case.get("expected") or []
    return len(exp) > 0


def _build_gold_set(expected: Sequence[dict], page_offset: int) -> set[Tuple[str, int]]:
    gold = set()
    for e in expected:
        src = _norm_source(e.get("source", ""))
        page = _safe_int(e.get("page", -1), -1)
        if page != -1:
            page = page + page_offset
        gold.add((src, page))
    return gold


def _match_expected(
    rows: list[dict],
    expected: list[dict],
    k: int,
    page_offset: int,
    page_tolerance: int,
) -> tuple[bool, float]:
    """
    expected: list of {source, page}
    rows: retrieved rows with {source, page}
    Returns: (hit_in_top_k, reciprocal_rank_or_0)
    """
    gold = _build_gold_set(expected, page_offset=0)  # gold as-is (we shift retrieved, not gold)
    top = rows[:k]

    rr = 0.0
    hit = False

    for i, r in enumerate(top):
        src = _norm_source(r.get("source", ""))
        page = _safe_int(r.get("page", -1), -1)

        # Apply offset to retrieved pages (common: DB is 0-index, gold is 1-index)
        if page != -1:
            page = page + page_offset

        # Exact match
        if (src, page) in gold:
            hit = True
            rr = 1.0 / (i + 1)
            break

        # Tolerance match (±1 etc.)
        if page_tolerance and page != -1:
            for d in range(1, page_tolerance + 1):
                if (src, page - d) in gold or (src, page + d) in gold:
                    hit = True
                    rr = 1.0 / (i + 1)
                    break
            if hit:
                break

    return hit, rr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/eval/retrieval_gold.jsonl")
    ap.add_argument("--out", default="data/eval/report.json")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--fail-under", type=float, default=None, help="Fail if Recall@K < threshold (0..1)")

    # NEW: to deal with page indexing mismatches
    ap.add_argument("--page-offset", type=int, default=0, help="Shift retrieved pages by this offset (e.g. +1)")
    ap.add_argument("--page-tolerance", type=int, default=0, help="Allow matching within ±tolerance pages (e.g. 1)")

    args = ap.parse_args()

    cases = _load_jsonl(args.data)

    gold_m = GoldMetrics()
    ne_m = NoEvidenceMetrics()

    details: list[dict[str, Any]] = []

    for case in cases:
        q = case["query"]
        expected = case.get("expected") or []

        rows, _dbg, _latency_ms = run_retrieval(q)

        has_gold = _case_has_gold(case)

        # --- No-evidence evaluation set ---
        if not has_gold:
            ne_m.n_no_evidence += 1
            predicted_empty = (len(rows) == 0)
            if predicted_empty:
                ne_m.no_evidence_correct += 1
            else:
                ne_m.false_evidence += 1

            details.append(
                {
                    "query": q,
                    "kind": "no_evidence",
                    "scored": False,
                    "expected": expected,
                    "retrieved": [{"source": r.get("source"), "page": r.get("page")} for r in rows[: args.k]],
                    "predicted_empty": predicted_empty,
                }
            )
            continue

        # --- Gold evaluation set ---
        gold_m.n_gold += 1
        hit, rr = _match_expected(
            rows=rows,
            expected=expected,
            k=args.k,
            page_offset=args.page_offset,
            page_tolerance=args.page_tolerance,
        )

        if hit:
            gold_m.recall_hits += 1
            gold_m.mrr_sum += rr

        details.append(
            {
                "query": q,
                "kind": "gold",
                "scored": True,
                "expected": expected,
                "hit": hit,
                "rr": rr,
                "retrieved": [{"source": r.get("source"), "page": r.get("page")} for r in rows[: args.k]],
                "retrieved_page_offset_applied": args.page_offset,
                "page_tolerance": args.page_tolerance,
            }
        )

    recall = (gold_m.recall_hits / gold_m.n_gold) if gold_m.n_gold else None
    mrr = (gold_m.mrr_sum / gold_m.n_gold) if gold_m.n_gold else None

    no_evidence_accuracy = (ne_m.no_evidence_correct / ne_m.n_no_evidence) if ne_m.n_no_evidence else None
    false_evidence_rate = (ne_m.false_evidence / ne_m.n_no_evidence) if ne_m.n_no_evidence else None

    report = {
        "k": args.k,
        "cases_total": len(cases),
        "cases_scored_gold": gold_m.n_gold,
        "recall_at_k": recall,
        "mrr": mrr,
        "no_evidence_total": ne_m.n_no_evidence,
        "no_evidence_accuracy": no_evidence_accuracy,
        "false_evidence_rate": false_evidence_rate,
        "page_offset": args.page_offset,
        "page_tolerance": args.page_tolerance,
        "details": details,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Console summary
    print("Retrieval Eval")
    print(f"- cases_total: {len(cases)}")
    print(f"- cases_scored_gold: {gold_m.n_gold}")
    print(f"- Recall@{args.k}: {recall}")
    print(f"- MRR: {mrr}")
    print(f"- no_evidence_total: {ne_m.n_no_evidence}")
    print(f"- no_evidence_accuracy: {no_evidence_accuracy}")
    print(f"- false_evidence_rate: {false_evidence_rate}")

    if args.fail_under is not None and recall is not None:
        if recall < args.fail_under:
            print(f"FAIL: Recall@{args.k} {recall:.3f} < {args.fail_under:.3f}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
