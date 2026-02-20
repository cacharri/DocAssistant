import argparse
from app.retrieval.retrieve import run_retrieval

def _clip(s: str, n: int = 220) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s[:n] + ("…" if len(s) > n else "")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    rows, dbg, latency_ms = run_retrieval(args.query)

    print(f"Query: {args.query}")
    print(f"Latency ms: {latency_ms:.1f}")
    if dbg:
        print(f"Debug: {dbg.get('timings_ms')}")

    if not rows:
        print("NO EVIDENCE")
        return 0

    for i, r in enumerate(rows[: args.k], start=1):
        print(f"\n#{i} score={r.get('_score')}")
        print(f"- source: {r.get('source')}")
        print(f"- page:   {r.get('page')}")
        print(f"- chunk:  {r.get('chunk_id')}")
        print(f"- text:   {_clip(r.get('text'))}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
