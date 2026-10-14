"""Probe retrieval: prints snippets + scores for an asset (calibrate thresholds)."""

import argparse
import sys

sys.path.insert(0, ".")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asset")
    ap.add_argument("--days", type=float, default=2.0)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    from src.config import load_config
    from src.strategy.state import connect_cfg
    cfg = load_config()
    conn = connect_cfg(cfg)
    from src.ai_agents.rag.retrieve import retrieve
    snippets, mode = retrieve(conn, cfg, args.asset.upper(),
                              max_age_hours=int(args.days * 24), top_k=args.top)
    print(f"mode={mode} n={len(snippets)}")
    for s in snippets:
        print(f"- [{s['score']:.3f}] [{s['id']}] {s['source']}: {s['title'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
