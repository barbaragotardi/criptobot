"""Metrics from project.md section 31 + group_by breakdowns."""

import pandas as pd


def f(x) -> float:
    return round(float(x), 2)


def summarize(trades: list[dict]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    df = pd.DataFrame(trades)
    wins = df[df["pnl_pct"] > 0]
    losses = df[df["pnl_pct"] <= 0]
    gross_win = wins["pnl_pct"].sum()
    gross_loss = -losses["pnl_pct"].sum()
    cum = (1 + df.sort_values("open_ts")["pnl_pct"] / 100).cumprod()
    drawdown = ((cum.cummax() - cum) / cum.cummax() * 100).max()
    max_loss_streak, cur = 0, 0
    for pnl in df.sort_values("open_ts")["pnl_pct"]:
        cur = cur + 1 if pnl <= 0 else 0
        max_loss_streak = max(max_loss_streak, cur)
    avg_win = wins["pnl_pct"].mean() if len(wins) else 0.0
    avg_loss = losses["pnl_pct"].mean() if len(losses) else 0.0
    win_rate = len(wins) / n
    return {
        "trades": n,
        "win_rate": round(win_rate * 100, 1),
        "loss_rate": round((1 - win_rate) * 100, 1),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        "return_total_pct": round((cum.iloc[-1] - 1) * 100, 1),
        "return_avg_pct": f(df["pnl_pct"].mean()),
        "best_pct": f(df["pnl_pct"].max()),
        "worst_pct": f(df["pnl_pct"].min()),
        "max_drawdown_pct": round(float(drawdown), 1),
        "max_loss_streak": max_loss_streak,
        "rr_avg": f(df["rr"].mean()),
        "expectancy_pct": f(win_rate * avg_win + (1 - win_rate) * avg_loss),
    }


def breakdown(trades: list[dict], by: str) -> dict:
    groups: dict[str, list] = {}
    for t in trades:
        key = t.get(by, "n/a")
        if by == "year":
            import datetime
            key = datetime.datetime.fromtimestamp(t["open_ts"] / 1000, tz=datetime.timezone.utc).year
        groups.setdefault(str(key), []).append(t)
    return {k: summarize(v) for k, v in sorted(groups.items())}
