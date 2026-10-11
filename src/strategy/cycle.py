"""One analysis cycle: market filter (once) -> per-asset pipeline (project.md section 5)."""

import logging
import time

import pandas as pd

from src.alerts.telegram import format_alert, format_paper_open, send_telegram
from src.costs import apply_entry
from src.confirmation.confirm import confirm
from src.exchange.client import fetch_ohlcv, fetch_warmup, make_exchange, symbol_for
from src.exposure.manager import exposure_ok, record_signal
from src.strategy.filters import evaluate_market_filter, macro_pass
from src.strategy.indicators import add_indicators
from src.paper.store import open_position, paper_enabled
from src.strategy.risk import calc_stop_method, find_resistance, calc_tp, position_size, risk_reward
from src.strategy.pullback import detect_pullback
from src.strategy.state import check_invalidation, get_state, in_cooldown, set_state

log = logging.getLogger(__name__)


def load_asset_frames(exchange, asset: str, cfg: dict) -> dict[str, pd.DataFrame]:
    quote = cfg["system"]["quote_currency"]
    symbol = symbol_for(asset, quote)
    tfmap = cfg["timeframe_map"]
    frames = {}
    for tf_key in ("1D", "4H", "15m"):
        warmup_n = cfg["data"]["warmup"][tf_key]
        df = fetch_warmup(exchange, symbol, tfmap[tf_key], warmup_n, quote)
        frames[tf_key] = add_indicators(df, cfg["ema"]["periods"], cfg["atr"]["period"])
    return frames


def evaluate_asset(asset: str, frames: dict, market_status: dict, conn, cfg: dict, now_ts: int | None = None) -> str:
    """`now_ts`: epoch seconds used for cooldown/watch/daily buckets. None = wall clock (production)."""
    tg = cfg["telegram"]
    dry_run = cfg["system"].get("dry_run", True)
    now = now_ts if now_ts is not None else int(time.time())
    state = get_state(conn, asset)

    # Stuck-state recovery: INVALIDATED never rearms by itself, and ALERT_SENT
    # only blocks while its cooldown is active. Without this, an asset that
    # already alerted (or was invalidated) can never generate a signal again.
    if state["state"] == "INVALIDATED":
        set_state(conn, asset, state="NO_SETUP", candles_15m_waited=0)
        state = get_state(conn, asset)

    if in_cooldown(state, now):
        log.info("%s - in cooldown, skip", asset)
        return "COOLDOWN"

    if state["state"] == "ALERT_SENT":
        # Cooldown already expired here (checked above): rearm for a fresh setup.
        set_state(conn, asset, state="NO_SETUP", candles_15m_waited=0)
        state = get_state(conn, asset)

    # Bearish market action
    if cfg["market_filter"].get("enabled") and not market_status["bullish"]:
        action = cfg["market_filter"].get("bearish_action", "BLOCK")
        if action == "BLOCK":
            log.info("%s - NO TRADE (market bearish, BLOCK)", asset)
            return "NO_TRADE"
        log.info("%s - market bearish, action=%s (proceeding, V1 logs only)", asset, action)

    df_1d, df_4h, df_15m = frames["1D"], frames["4H"], frames["15m"]

    # --- Macro filter 1D (BTC reuses market result for close>ema200 part) ---
    ok, reason = macro_pass(df_1d, cfg)
    log.info("%s - Macro filter: %s (%s)", asset, "PASS" if ok else "FAIL", reason)
    if not ok:
        if state["state"] == "WATCHING":
            set_state(conn, asset, state="INVALIDATED")
        return "NO_TRADE"

    # --- Invalidation of open WATCHING ---
    if state["state"] in ("WATCHING", "TOUCHED_EMA"):
        invalid, inv_reason = check_invalidation(df_4h, state, cfg)
        waited = (state.get("candles_15m_waited") or 0) + 1
        if invalid:
            set_state(conn, asset, state="INVALIDATED", candles_15m_waited=0)
            log.info("%s - setup invalidated: %s", asset, inv_reason)
            return "INVALIDATED"
        if waited > cfg["invalidation"]["max_15m_candles_without_confirmation"]:
            set_state(conn, asset, state="NO_SETUP", candles_15m_waited=0)
            log.info("%s - setup timeout, back to NO_SETUP", asset)
            return "TIMEOUT"
        set_state(conn, asset, candles_15m_waited=waited)

    # --- Pullback 4H ---
    pb = detect_pullback(df_4h, cfg)
    if not pb["valid"]:
        log.info("%s - 4H no pullback (%s)", asset, pb["reason"])
        return "NO_SETUP"
    log.info("%s - 4H EMA%s touch detected", asset, pb["ema"])
    if state["state"] == "NO_SETUP":
        ok_exp, exp_reason = exposure_ok(conn, asset, cfg, now)
        if not ok_exp:
            log.info("%s - WATCHING blocked (exposure: %s)", asset, exp_reason)
            return "NO_SETUP"
        set_state(
            conn, asset, state="WATCHING", ema=pb["ema"],
            pullback_low=pb["pullback_low"], candles_15m_waited=0,
            watching_since_ts=now,
        )
        state = get_state(conn, asset)

    # --- Confirmation 15m (V1: only after fresh touch; state WATCHING required) ---
    if state["state"] not in ("WATCHING", "TOUCHED_EMA"):
        return "WATCHING"
    confirmed, conf_reason = confirm(
        df_15m, cfg["confirmation"].get("method", "reversal"),
        ema_value=float(df_4h.iloc[-1][f"ema{pb['ema']}"]),
    )
    log.info("%s - 15m confirmation: %s (%s)", asset, "PASS" if confirmed else "WAIT", conf_reason)
    if not confirmed:
        return "WATCHING"

    entry = float(df_15m.iloc[-1]["close"])
    atr_4h = float(df_4h.iloc[-1]["atr"])
    stop = calc_stop_method(cfg["risk"].get("stop_method", "structure_atr"), entry,
                            state["pullback_low"] or pb["pullback_low"], atr_4h, cfg["risk"]["atr_multiplier"])
    resistance = find_resistance(df_4h, cfg["target"]["resistance_lookback_4h"])
    tp, target_class = calc_tp(entry, resistance, cfg)
    ret_pct = (tp - entry) / entry * 100
    risk_pct = (entry - stop) / entry * 100
    log.info("%s - Stop calculated: %.1f%%", asset, risk_pct)
    log.info("%s - Resistance distance: %.1f%%", asset, (resistance - entry) / entry * 100)
    log.info("%s - TP calculated: %.1f%%", asset, ret_pct)

    if target_class == "REJECT":
        log.info("%s - SIGNAL REJECTED (return %.1f%% below absolute minimum)", asset, ret_pct)
        return "REJECTED"
    rr = risk_reward(entry, stop, tp)
    log.info("%s - Risk/Reward: %.1f", asset, rr)
    if rr < cfg["risk"]["min_risk_reward"]:
        log.info("%s - SIGNAL REJECTED (R/R below minimum, stop NOT tightened)", asset)
        return "REJECTED"

    ok_exp, exp_reason = exposure_ok(conn, asset, cfg, now)
    if not ok_exp:
        log.info("%s - SIGNAL REJECTED (exposure: %s)", asset, exp_reason)
        return "REJECTED"

    balance = cfg["risk"]["simulated_account_balance"]
    pos_usd, cap_risk = position_size(balance, cfg["risk"]["max_risk_per_trade_percent"], entry, stop)
    log.info("%s - Position size: $%.0f", asset, pos_usd)

    btc_status = "Bullish" if market_status["bullish"] else "Bearish"
    text = format_alert(asset, pb["ema"], entry, stop, tp, risk_pct, ret_pct, rr,
                        balance, cap_risk, pos_usd, resistance, target_class, btc_status)
    sent = send_telegram(tg["bot_token"], tg["chat_id"], text, dry_run=dry_run)
    if sent:
        cooldown_until = now + cfg["system"]["cooldown_hours"] * 3600
        set_state(conn, asset, state="ALERT_SENT", entry=entry, stop=stop, tp=tp,
                  rr=rr, last_alert_ts=now, cooldown_until_ts=cooldown_until,
                  candles_15m_waited=0)
        record_signal(conn, now)
        log.info("%s - SIGNAL GENERATED", asset)
        return "SIGNAL"
    return "SEND_FAILED"


def run_cycle(cfg: dict, conn, exchange=None) -> dict[str, str]:
    """Single cycle over all assets. Market filter computed once."""
    exchange = exchange or make_exchange()
    ref = cfg["market_filter"]["reference_asset"]
    btc_frames = load_asset_frames(exchange, ref, cfg)
    market_status = evaluate_market_filter(btc_frames["1D"], cfg)

    results: dict[str, str] = {}
    frames_cache = {ref: btc_frames}
    for asset in cfg["assets"]:
        try:
            frames = frames_cache.get(asset) or load_asset_frames(exchange, asset, cfg)
            res = evaluate_asset(asset, frames, market_status, conn, cfg)
            results[asset] = res
            if res == "SIGNAL" and paper_enabled(cfg):
                _open_paper_position(conn, asset, market_status, cfg)
        except Exception as e:
            log.error("%s - cycle error: %s", asset, e)
            results[asset] = "ERROR"
    return results


def _open_paper_position(conn, asset: str, market_status: dict, cfg: dict) -> None:
    """V4: every SIGNAL opens a virtual position (fire-and-forget). Dedup: 1 OPEN per asset."""
    now_ms = int(time.time() * 1000)
    st = get_state(conn, asset)
    entry_eff = apply_entry(st["entry"], cfg)
    balance = cfg["risk"]["simulated_account_balance"]
    pos_usd, cap_risk = position_size(
        balance, cfg["risk"]["max_risk_per_trade_percent"], st["entry"], st["stop"])
    pid = open_position(
        conn, asset,
        open_ts=now_ms, ema=st["ema"], entry=entry_eff, stop=st["stop"], tp=st["tp"],
        rr=st["rr"], position_usd=pos_usd, capital_risk=cap_risk,
        stop_method=cfg["risk"].get("stop_method", "structure_atr"),
        confirm_method=cfg["confirmation"].get("method", "reversal"),
        btc_bullish=int(market_status["bullish"]),
    )
    if pid is None:
        log.info("%s - paper position already OPEN, skip", asset)
        return
    log.info("%s - PAPER OPEN #%d @ %.2f", asset, pid, entry_eff)
    tg = cfg["telegram"]
    text = format_paper_open(asset, entry_eff, st["stop"], st["tp"], st["rr"], pos_usd)
    if not send_telegram(tg["bot_token"], tg["chat_id"], text,
                         dry_run=cfg["system"].get("dry_run", True)):
        log.warning("%s - paper open alert NOT sent", asset)
