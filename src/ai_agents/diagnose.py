"""Read-only technical diagnosis for /analyze (no state writes, no Telegram)."""

import logging

log = logging.getLogger(__name__)


def diagnose_text(conn, exchange, cfg, asset: str) -> str:
    """Structured facts: market filter, macro, pullback, state, supports. Pure reads."""
    from src.exchange.client import symbol_for
    from src.strategy.filters import evaluate_market_filter, macro_pass
    from src.strategy.indicators import add_indicators
    from src.strategy.pullback import detect_pullback
    from src.strategy.state import get_state
    from src.supports.calc import compute_supports

    quote = cfg["system"]["quote_currency"]
    ref = cfg.get("market_filter", {}).get("reference_asset", "BTC")
    facts: list[str] = []
    try:
        st = get_state(conn, asset)
        facts.append(f"estado={st.get('state')}")
    except Exception as e:
        facts.append(f"estado=erro({e})")
    try:
        import pandas as pd

        def _frame(sym: str, tf: str, n: int):
            raw = exchange.fetch_ohlcv(symbol_for(sym, quote), timeframe=tf, limit=n + 5)
            import pandas as pd
            df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "vol"])
            return add_indicators(df, cfg["ema"]["periods"], cfg["atr"]["period"])

        mkt = evaluate_market_filter(_frame(ref, "1d", 250), cfg)
        facts.append(f"market_bullish={mkt.get('bullish')}")
        d1 = _frame(asset, "1d", 250)
        ok, reason = macro_pass(d1, cfg)
        facts.append(f"macro_1d={'PASS' if ok else 'FAIL'}({reason})")
        h4 = _frame(asset, "4h", 300)
        pb = detect_pullback(h4, cfg)
        facts.append(f"pullback_4h={'TOUCH_EMA' + str(pb.get('ema')) if pb.get('valid') else 'NO(' + str(pb.get('reason')) + ')'}")
        try:
            sup = compute_supports(d1.tail(120), cfg)
            facts.append(f"suportes=${sup['zone'][0]:,.0f}-${sup['zone'][1]:,.0f}" if sup.get("zone", (None, None))[0] else "suportes=n/a")
        except Exception:
            facts.append("suportes=n/a")
    except Exception as e:
        facts.append(f"frames_erro={e}")
    return "; ".join(facts)
