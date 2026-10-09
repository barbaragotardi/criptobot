"""Telegram inbound listener: long-poll getUpdates, dispatch portfolio commands."""

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts.telegram import (
    format_delete_confirmation,
    format_edit_confirmation,
    format_extrato,
    format_historico,
    format_sell_confirmation,
    format_trade_confirmation,
    get_updates,
    send_telegram,
)
from src.exchange.client import make_exchange, symbol_for
from src.portfolio.parser import parse_command, parse_delete, parse_edit, validate_asset
from src.portfolio.pricing import price_at
from src.portfolio.store import (
    consume_fifo,
    delete_trade,
    get_trade,
    list_trades,
    matches_for_asset,
    open_buy_qty,
    realized_pnl,
    recompute_fifo,
    record_trade,
    update_trade_price,
    update_trade_qty,
    update_trade_time,
    weighted_avg,
)
from src.setup.state import connect as connect_db

log = logging.getLogger(__name__)


def get_offset(conn) -> int:
    row = conn.execute("SELECT last_update_id FROM telegram_offset WHERE id=1").fetchone()
    return row[0] if row else 0


def set_offset(conn, update_id: int) -> None:
    conn.execute(
        "INSERT INTO telegram_offset (id, last_update_id) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_update_id=excluded.last_update_id",
        (update_id,),
    )
    conn.commit()


def current_prices(conn, exchange, cfg, assets: list[str]) -> dict[str, float]:
    quote = cfg["system"]["quote_currency"]
    out: dict[str, float] = {}
    for asset in assets:
        try:
            raw = exchange.fetch_ohlcv(symbol_for(asset, quote), timeframe="1m", limit=2)
            if raw:
                out[asset] = float(raw[-1][4])
        except Exception as e:
            log.warning("extrato price %s failed: %s", asset, e)
    return out


def handle_text(text: str, message_id: int, conn, exchange, cfg) -> str:
    """Process one message, persist, and return the reply text."""
    tg_chat = str(cfg["telegram"]["chat_id"])
    _ = tg_chat  # chat check happens in run_listener; direct calls skip it
    cmd = (text or "").strip()
    if cmd.lower().startswith("/extrato"):
        parts = cmd.split()
        asset = parts[1].upper() if len(parts) > 1 else None
        if asset:
            validate_asset(asset, cfg)
        rows = [r for r in list_trades(conn, asset)
                if r["side"] == "BUY" and (r.get("remaining_qty") or 0) > 0]
        if not rows:
            return "📋 EXTRATO · posições em aberto\n\n📭 Nenhuma posição em aberto."
        assets = sorted({r["asset"] for r in rows})
        avgs = {}
        for a in assets:
            avg, qty = weighted_avg(conn, a, "BUY")
            if qty:
                avgs[(a, "BUY")] = (avg, qty)
        prices = current_prices(conn, exchange, cfg, assets)
        return format_extrato(rows, avgs, prices)

    if cmd.lower().startswith("/historico"):
        parts = cmd.split()
        asset = parts[1].upper() if len(parts) > 1 else None
        if asset:
            validate_asset(asset, cfg)
        rows = [r for r in list_trades(conn, asset) if r["side"] == "SELL"]
        if not rows:
            return "📜 HISTÓRICO · vendas realizadas\n\n📭 Nenhuma venda registrada."
        assets = sorted({r["asset"] for r in rows})
        matches_by_sell: dict = {}
        realized = {}
        for a in assets:
            for m in matches_for_asset(conn, a):
                matches_by_sell.setdefault(m["sell_trade_id"], []).append(m)
            pnl, matched = realized_pnl(conn, a)
            if matched:
                realized[a] = (pnl, matched)
        return format_historico(rows, matches_by_sell, realized)

    if cmd.lower().startswith("/edit"):
        trade_id, field, raw = parse_edit(cmd)
        tr = get_trade(conn, trade_id)
        if tr is None:
            raise ValueError(f"Registro #{trade_id} não encontrado.")
        if field == "QTY":
            new_qty = float(raw.replace(",", "."))
            old = f"{tr['quantity']:g}"
            update_trade_qty(conn, trade_id, new_qty, commit=False)
            recompute_fifo(conn, tr["asset"])
            return format_edit_confirmation(
                trade_id, tr["asset"], tr["side"], "Quantidade", old, f"{new_qty:g}")
        if field == "PRICE":
            new_price = float(raw.replace(",", "."))
            old = f"${tr['price']:,.2f}"
            update_trade_price(conn, trade_id, new_price, commit=False)
            recompute_fifo(conn, tr["asset"])
            return format_edit_confirmation(
                trade_id, tr["asset"], tr["side"], "Preço", old, f"${new_price:,.2f}")
        quote = cfg["system"]["quote_currency"]
        price, trade_ts_ms, fallback = price_at(
            exchange, symbol_for(tr["asset"], quote), raw, cfg)
        tz = ZoneInfo(cfg["system"].get("timezone", "America/Sao_Paulo"))
        old_hhmm = datetime.fromtimestamp(tr["trade_ts"] / 1000, tz).strftime("%H:%M")
        update_trade_time(conn, trade_id, trade_ts_ms, price, fallback, commit=False)
        recompute_fifo(conn, tr["asset"])
        reply = format_edit_confirmation(
            trade_id, tr["asset"], tr["side"], "Horário",
            old_hhmm, f"{raw} (preço ${price:,.2f})")
        if fallback:
            reply += "\n⚠️ Preço atual (candle do horário ainda não fechado)."
        return reply

    if cmd.lower().startswith("/delete"):
        trade_id = parse_delete(cmd)
        tr = get_trade(conn, trade_id)
        if tr is None:
            raise ValueError(f"Registro #{trade_id} não encontrado.")
        delete_trade(conn, trade_id, commit=False)
        recompute_fifo(conn, tr["asset"])
        return format_delete_confirmation(tr)

    side, asset, hhmm, qty = parse_command(cmd)
    validate_asset(asset, cfg)
    quote = cfg["system"]["quote_currency"]
    price, trade_ts_ms, fallback = price_at(exchange, symbol_for(asset, quote), hhmm, cfg)
    if side == "SELL":
        avail = open_buy_qty(conn, asset)
        if qty > avail:
            raise ValueError(
                f"Venda de {qty:g} {asset} maior que a posição aberta ({avail:g}). "
                "Não registrada."
            )
    trade_id = record_trade(conn, asset, side, trade_ts_ms, qty, price, fallback, message_id)
    if side == "SELL":
        matches = consume_fifo(conn, asset, trade_id, qty, price)
        return format_sell_confirmation(asset, qty, price, qty * price, fallback, matches)
    return format_trade_confirmation(side, asset, qty, price, qty * price, fallback)


def run_listener(cfg: dict, conn, exchange=None) -> None:
    """Blocking loop. Each thread/process must use its own sqlite connection."""
    if exchange is None:
        exchange = make_exchange()
    if conn is None:
        conn = connect_db(cfg["system"]["db_path"])
    tg = cfg["telegram"]
    timeout = cfg["system"].get("telegram_poll_timeout_s", 30)
    log.info("telegram listener starting")
    while True:
        try:
            offset = get_offset(conn) + 1
            updates = get_updates(tg["bot_token"], offset, timeout)
            for u in updates:
                set_offset(conn, u["update_id"])
                msg = u.get("message") or {}
                chat_id = str((msg.get("chat") or {}).get("id", ""))
                if chat_id != str(tg["chat_id"]):
                    continue
                text = msg.get("text", "")
                message_id = msg.get("message_id")
                if not text.startswith("/"):
                    continue
                try:
                    reply = handle_text(text, message_id, conn, exchange, cfg)
                except (ValueError, RuntimeError) as e:
                    reply = f"❌ {e}"
                    log.warning("command failed %r: %s", text, e)
                send_telegram(tg["bot_token"], tg["chat_id"], reply,
                              dry_run=cfg["system"].get("dry_run", True))
        except Exception as e:
            log.error("listener loop error: %s", e)
            time.sleep(10)
