"""Telegram alert: template from project.md section 28."""

import logging
import requests

log = logging.getLogger(__name__)


def format_alert(
    asset: str,
    setup_ema: int,
    entry: float,
    stop: float,
    tp: float,
    risk_pct: float,
    ret_pct: float,
    rr: float,
    balance: float,
    capital_risk: float,
    position_usd: float,
    resistance: float,
    target_class: str,
    btc_status: str,
) -> str:
    return (
        "🟢 SETUP CONFIRMADO\n"
        f"\nAtivo: {asset}\n"
        f"Setup: Pullback EMA{setup_ema}\n"
        "Timeframe: 4H\n"
        "Confirmação: 15m\n"
        "\nTendência 1D:\n"
        "Preço > EMA200\n"
        "EMA200 inclinada positivamente\n"
        f"\nEntrada: ${entry:,.2f}\n"
        f"Stop: ${stop:,.2f}\n"
        f"Take Profit: ${tp:,.2f}\n"
        f"\nRisco: {risk_pct:.1f}%\n"
        f"Retorno potencial: {ret_pct:.1f}%\n"
        f"Risk/Reward: {rr:.1f}\n"
        f"\nSaldo de referência: ${balance:,.0f}\n"
        f"Risco financeiro: ${capital_risk:,.0f}\n"
        f"Posição sugerida: ${position_usd:,.0f}\n"
        f"\nResistência relevante: ${resistance:,.2f}\n"
        f"\nClassificação do alvo:\n{target_class}\n"
        f"\nStatus BTC:\n{btc_status}\n"
        "\n⚠️ Alerta baseado em critérios técnicos.\n"
        "Não representa garantia de resultado."
    )


def format_paper_open(asset: str, entry: float, stop: float, tp: float,
                      rr: float, position_usd: float) -> str:
    return (
        "📝 PAPER ABERTA (virtual, sem ordem real)\n"
        f"\nAtivo: {asset}\n"
        f"\nEntrada: ${entry:,.2f}\n"
        f"Stop: ${stop:,.2f}\n"
        f"Take Profit: ${tp:,.2f}\n"
        f"\nRisk/Reward: {rr:.1f}\n"
        f"Posição virtual: ${position_usd:,.0f}\n"
    )


def format_paper_close(asset: str, reason: str, exit_price: float,
                       pnl_pct: float, pnl_usd: float) -> str:
    emoji = "✅" if pnl_pct > 0 else "🛑"
    return (
        f"{emoji} PAPER FECHADA ({reason})\n"
        f"\nAtivo: {asset}\n"
        f"Saída: ${exit_price:,.2f}\n"
        f"PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})\n"
        "\nPosição virtual, sem ordem real."
    )


def get_updates(bot_token: str, offset: int = 0, timeout: int = 30) -> list[dict]:
    """Long-poll Telegram getUpdates. Returns list of update dicts (may be empty)."""
    r = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getUpdates",
        params={"offset": offset, "timeout": timeout},
        timeout=timeout + 10,
    )
    if r.status_code != 200:
        log.error("Telegram getUpdates failed: %s %s", r.status_code, r.text[:200])
        return []
    return r.json().get("result", [])


def _trend_emoji(pct: float) -> str:
    return "🟢" if pct >= 0 else "🔴"


def format_trade_confirmation(side: str, asset: str, qty: float, price: float,
                              cost: float, fallback: bool) -> str:
    op = "COMPRA" if side == "BUY" else "VENDA"
    emoji = "🛒" if side == "BUY" else "💸"
    extra = "\n\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    return (
        f"✅ {op} REGISTRADA\n"
        f"\n{emoji} Ativo: {asset}\n"
        f"🔢 Quantidade: {qty:g}\n"
        f"💲 Preço: ${price:,.2f}\n"
        f"💰 Valor: ${cost:,.2f}"
        f"{extra}"
    )


def format_portfolio_alert(asset: str, side: str, ref_price: float,
                            current: float, pct: float, threshold: float,
                            scope: str) -> str:
    direction = "subiu" if side == "BUY" else "caiu"
    ref_label = "Preço médio" if scope == "media" else "Preço da compra/venda"
    emoji = "🚀" if side == "BUY" else "📉"
    return (
        f"{emoji} {asset} {direction} {pct:.1f}% (meta {threshold:.0f}%)\n"
        f"\n📊 {ref_label}: ${ref_price:,.2f}\n"
        f"💲 Preço atual: ${current:,.2f}\n"
    )


def format_sell_confirmation(asset: str, qty: float, price: float,
                             cost: float, fallback: bool,
                             matches: list[dict]) -> str:
    extra = "\n\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    lines = [
        "✅ VENDA REGISTRADA",
        f"\n💸 Ativo: {asset}\n"
        f"🔢 Quantidade: {qty:g}\n"
        f"💲 Preço: ${price:,.2f}\n"
        f"💰 Valor: ${cost:,.2f}"
        f"{extra}",
        "\n📦 Lotes abatidos (FIFO):",
    ]
    total_pnl = 0.0
    for m in matches:
        total_pnl += m["pnl_usd"]
        lines.append(
            f"{_trend_emoji(m['pnl_pct'])} {m['qty']:g} @ ${m['buy_price']:,.2f} "
            f"→ PnL: ${m['pnl_usd']:+,.2f} ({m['pnl_pct']:+.1f}%)"
        )
    lines.append(f"\n🏁 PnL realizado nesta venda: ${total_pnl:+,.2f} {_trend_emoji(total_pnl)}")
    return "\n".join(lines)


def format_extrato(rows: list[dict], avgs: dict, prices: dict) -> str:
    """Open BUY positions with % variation vs current price."""
    lines = ["📋 EXTRATO · posições em aberto"]
    for asset in sorted({r["asset"] for r in rows}):
        current = prices.get(asset, 0)
        lines.append(f"\n🪙 {asset} — atual: ${current:,.2f}")
        for r in [x for x in rows if x["asset"] == asset]:
            line = (
                f"#{r['id']} COMPRA {r['quantity']:g} @ ${r['price']:,.2f} "
                f"(${r['cost_usd']:,.2f})"
            )
            if current:
                pct = (current - r["price"]) / r["price"] * 100
                line += f" {_trend_emoji(pct)} ({pct:+.1f}% vs atual)"
            lines.append(line)
        key = (asset, "BUY")
        if key in avgs:
            avg, qty = avgs[key]
            suffix = ""
            if current:
                pct = (current - avg) / avg * 100
                suffix = (f" | Posição: ${qty * current:,.2f} "
                          f"({_trend_emoji(pct)} {pct:+.1f}%)")
            lines.append(f"📊 Média compra: ${avg:,.2f} (qtd aberta {qty:g}){suffix}")
    return "\n".join(lines)


def format_historico(rows: list[dict], matches_by_sell: dict,
                     realized: dict | None = None) -> str:
    """Realized sales with per-lot PnL."""
    realized = realized or {}
    if not rows:
        return "📜 HISTÓRICO · vendas realizadas\n\n📭 Nenhuma venda registrada."
    lines = ["📜 HISTÓRICO · vendas realizadas"]
    for asset in sorted({r["asset"] for r in rows}):
        lines.append(f"\n💰 {asset}")
        for r in [x for x in rows if x["asset"] == asset]:
            sell_matches = matches_by_sell.get(r["id"], [])
            sell_pnl = sum(m["pnl_usd"] for m in sell_matches)
            lines.append(
                f"#{r['id']} VENDA {r['quantity']:g} @ ${r['price']:,.2f} "
                f"(${r['cost_usd']:,.2f}) {_trend_emoji(sell_pnl)}"
            )
            for m in sell_matches:
                lines.append(
                    f"  ↳ lote #{m['buy_trade_id']}: {m['qty']:g} "
                    f"@ ${m['buy_price']:,.2f} "
                    f"→ PnL: ${m['pnl_usd']:+,.2f} ({m['pnl_pct']:+.1f}%) "
                    f"{_trend_emoji(m['pnl_pct'])}"
                )
        if asset in realized:
            pnl, matched = realized[asset]
            lines.append(f"🏁 PnL realizado: ${pnl:+,.2f} (qtd vendida {matched:g}) "
                         f"{_trend_emoji(pnl)}")
    return "\n".join(lines)


def format_edit_confirmation(trade_id: int, asset: str, side: str,
                             field_label: str, old_val: str, new_val: str) -> str:
    op = "COMPRA" if side == "BUY" else "VENDA"
    return (
        "✏️ REGISTRO EDITADO\n"
        f"\n🪙 #{trade_id} {op} {asset}\n"
        f"🔄 {field_label}: {old_val} → {new_val}\n"
        "\n📦 FIFO recalculado para o ativo."
    )


def format_delete_confirmation(trade: dict) -> str:
    op = "COMPRA" if trade["side"] == "BUY" else "VENDA"
    return (
        "🗑️ REGISTRO APAGADO\n"
        f"\n🪙 #{trade['id']} {op} {trade['quantity']:g} {trade['asset']} "
        f"@ ${trade['price']:,.2f}\n"
        "\n📦 FIFO recalculado para o ativo."
    )


def send_telegram(bot_token: str, chat_id: str, text: str, dry_run: bool = True) -> bool:
    if dry_run:
        log.info("[DRY-RUN] Telegram message suppressed:\n%s", text)
        return True
    if not bot_token or not chat_id:
        log.error("Telegram credentials missing; alert NOT sent")
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    if r.status_code != 200:
        log.error("Telegram send failed: %s %s", r.status_code, r.text[:200])
        return False
    return True
