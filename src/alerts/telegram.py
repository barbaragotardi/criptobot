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


def format_trade_confirmation(side: str, asset: str, qty: float, price: float,
                              cost: float, fallback: bool) -> str:
    op = "COMPRA" if side == "BUY" else "VENDA"
    extra = "\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    return (
        f"✅ {op} REGISTRADA\n"
        f"\nAtivo: {asset}\n"
        f"Quantidade: {qty:g}\n"
        f"Preço: ${price:,.2f}\n"
        f"Valor: ${cost:,.2f}\n"
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
        f"\n{ref_label}: ${ref_price:,.2f}\n"
        f"Preço atual: ${current:,.2f}\n"
    )


def format_sell_confirmation(asset: str, qty: float, price: float,
                             cost: float, fallback: bool,
                             matches: list[dict]) -> str:
    extra = "\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    lines = [
        "✅ VENDA REGISTRADA",
        f"\nAtivo: {asset}\n"
        f"Quantidade: {qty:g}\n"
        f"Preço: ${price:,.2f}\n"
        f"Valor: ${cost:,.2f}\n"
        f"{extra}",
        "\nLotes abatidos (FIFO):",
    ]
    total_pnl = 0.0
    for m in matches:
        total_pnl += m["pnl_usd"]
        lines.append(
            f"- {m['qty']:g} @ ${m['buy_price']:,.2f} "
            f"→ PnL: ${m['pnl_usd']:+,.2f} ({m['pnl_pct']:+.1f}%)"
        )
    lines.append(f"\nPnL realizado nesta venda: ${total_pnl:+,.2f}")
    return "\n".join(lines)


def format_extrato(rows: list[dict], avgs: dict, prices: dict,
                   realized: dict | None = None) -> str:
    realized = realized or {}
    lines = ["📋 EXTRATO"]
    for asset in sorted({r["asset"] for r in rows}):
        lines.append(f"\n— {asset} (atual: ${prices.get(asset, 0):,.2f}) —")
        for r in [x for x in rows if x["asset"] == asset]:
            op = "COMPRA" if r["side"] == "BUY" else "VENDA"
            line = (
                f"#{r['id']} {op} {r['quantity']:g} @ ${r['price']:,.2f} "
                f"(${r['cost_usd']:,.2f})"
            )
            if r["side"] == "BUY":
                line += f" (aberto: {r.get('remaining_qty', r['quantity']):g})"
            lines.append(line)
        for side in ("BUY", "SELL"):
            key = (asset, side)
            if key in avgs:
                avg, qty = avgs[key]
                label = "Média compra" if side == "BUY" else "Média venda"
                lines.append(f"{label}: ${avg:,.2f} (qtd total {qty:g})")
        if asset in realized:
            pnl, matched = realized[asset]
            lines.append(f"PnL realizado: ${pnl:+,.2f} (qtd vendida {matched:g})")
    return "\n".join(lines)


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
