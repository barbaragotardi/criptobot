"""Run council once for an asset. --fake uses stub LLM (no API cost)."""

import argparse
import json
import sys

sys.path.insert(0, ".")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--fake", action="store_true")
    args = ap.parse_args()
    from src.config import load_config
    cfg = load_config()
    if args.fake:
        import src.ai_agents.agents as ag
        from src.ai_agents.schemas import Briefing, NewsView, RiskView
        ag.run_news = lambda conn, cfg, sn: NewsView(sentiment="neutral")
        ag.run_risk = lambda conn, cfg, f: RiskView(concentration="low", flags=[])
        ag.run_chief = lambda conn, cfg, n, r, a, s: Briefing(
            tone="neutral", bullets=["stub: briefing fake"])
    from src.strategy.state import connect_cfg
    conn = connect_cfg(cfg)
    from src.ai_agents.council import run_council
    res = run_council(args.asset.upper(), cfg, conn)
    print(json.dumps(res, indent=2, default=str) if res else "NO_RESULT (disabled or failed)")


if __name__ == "__main__":
    main()
