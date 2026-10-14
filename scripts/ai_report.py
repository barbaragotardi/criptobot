"""Cost/latency report from ai_calls + council outcomes."""

import sys

sys.path.insert(0, ".")

from src.config import load_config
from src.strategy.state import connect_cfg


def main() -> None:
    cfg = load_config()
    conn = connect_cfg(cfg)
    rows = conn.execute(
        "SELECT agent, COUNT(*), AVG(latency_ms), SUM(prompt_tokens),"
        " SUM(completion_tokens), SUM(cost_usd), SUM(ok) FROM ai_calls GROUP BY agent"
    ).fetchall()
    print(f"{'agent':28s} {'n':>4s} {'lat_ms':>8s} {'ptok':>8s} {'ctok':>8s} {'cost':>10s} {'ok':>4s}")
    for a, n, lat, pt, ct, cost, ok in rows:
        print(f"{a:28s} {n:4d} {float(lat or 0):8.0f} {int(pt or 0):8d}"
              f" {int(ct or 0):8d} {float(cost or 0):10.4f} {int(ok or 0):4d}")
    reps = conn.execute(
        "SELECT asset, COUNT(*), SUM(ok) FROM council_reports GROUP BY asset").fetchall()
    print("\ncouncil_reports:")
    for a, n, ok in reps:
        print(f"  {a}: {n} total, {ok} ok")


if __name__ == "__main__":
    main()
