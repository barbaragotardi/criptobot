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
                              cost: float, fallback: bool,
                              when: str | None = None) -> str:
    op = "COMPRA" if side == "BUY" else "VENDA"
    emoji = "🛒" if side == "BUY" else "💸"
    extra = "\n\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    when_line = f"\n📅 Data: {when}" if when else ""
    return (
        f"✅ {op} REGISTRADA\n"
        f"\n{emoji} Ativo: {asset}\n"
        f"🔢 Quantidade: {qty:g}\n"
        f"💲 Preço: ${price:,.2f}\n"
        f"💰 Valor: ${cost:,.2f}"
        f"{when_line}"
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
                             matches: list[dict],
                             when: str | None = None) -> str:
    extra = "\n\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    when_line = f"\n📅 Data: {when}" if when else ""
    lines = [
        "✅ VENDA REGISTRADA",
        f"\n💸 Ativo: {asset}\n"
        f"🔢 Quantidade: {qty:g}\n"
        f"💲 Preço: ${price:,.2f}\n"
        f"💰 Valor: ${cost:,.2f}"
        f"{when_line}"
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


def format_troca_confirmation(asset_from: str, qty_from: float, price_from: float,
                              asset_to: str, qty_to: float, price_to: float,
                              fallback: bool, matches: list[dict],
                              when: str | None = None) -> str:
    """Swap confirmation: SELL leg (FIFO) + BUY leg."""
    extra = "\n\n⚠️ Preço atual (candle do horário ainda não fechado)." if fallback else ""
    when_line = f"\n📅 Data: {when}" if when else ""
    lines = [
        "✅ TROCA REGISTRADA",
        f"\n💸 Vendeu: {qty_from:g} {asset_from} @ ${price_from:,.2f} "
        f"(${qty_from * price_from:,.2f})",
        f"🛒 Comprou: {qty_to:g} {asset_to} @ ${price_to:,.2f} "
        f"(${qty_to * price_to:,.2f})"
        f"{when_line}"
        f"{extra}",
        f"\n📦 Lotes {asset_from} abatidos (FIFO):",
    ]
    total_pnl = 0.0
    for m in matches:
        total_pnl += m["pnl_usd"]
        lines.append(
            f"{_trend_emoji(m['pnl_pct'])} {m['qty']:g} @ ${m['buy_price']:,.2f} "
            f"→ PnL: ${m['pnl_usd']:+,.2f} ({m['pnl_pct']:+.1f}%)"
        )
    lines.append(f"\n🏁 PnL realizado nesta troca: ${total_pnl:+,.2f} {_trend_emoji(total_pnl)}")
    return "\n".join(lines)


SEP = "➖➖➖➖➖➖➖➖"


def format_extrato(rows: list[dict], avgs: dict, prices: dict) -> str:
    """Open BUY positions: portfolio summary + per-asset blocks with allocation."""
    assets = sorted({r["asset"] for r in rows})
    stats: dict[str, dict] = {}
    for a in assets:
        avg, qty = avgs.get((a, "BUY"), (0.0, 0.0))
        current = prices.get(a, 0)
        invested = avg * qty
        value = qty * current if current else 0.0
        pct = (current - avg) / avg * 100 if current and avg else None
        stats[a] = {"avg": avg, "qty": qty, "current": current,
                    "invested": invested, "value": value, "pct": pct}
    total_invested = sum(s["invested"] for s in stats.values())
    total_value = sum(s["value"] for s in stats.values())
    total_pnl = total_value - total_invested
    total_pct = total_pnl / total_invested * 100 if total_invested else None

    lines = ["<b>📋 EXTRATO</b> · posições em aberto"]
    lines.append("")
    lines.append(f"💼 Investido: <b>${total_invested:,.2f}</b>")
    lines.append(f"💰 Valor atual: <b>${total_value:,.2f}</b>")
    if total_pct is None:
        lines.append(f"📈 Resultado: <b>${total_pnl:+,.2f}</b>")
    else:
        emoji = "📈" if total_pnl >= 0 else "📉"
        lines.append(f"{emoji} Resultado: <b>${total_pnl:+,.2f} ({total_pct:+.1f}%)</b> "
                     f"{_trend_emoji(total_pnl)}")

    ranked = [(a, s["pct"]) for a, s in stats.items() if s["pct"] is not None]
    if len(ranked) >= 2:
        best = max(ranked, key=lambda x: x[1])
        worst = min(ranked, key=lambda x: x[1])
        lines.append("")
        lines.append(f"🏆 Melhor posição: <b>{best[0]}</b> {best[1]:+.1f}% "
                     f"{_trend_emoji(best[1])}")
        lines.append(f"🥶 Pior posição: <b>{worst[0]}</b> {worst[1]:+.1f}% "
                     f"{_trend_emoji(worst[1])}")

    for asset in assets:
        s = stats[asset]
        lines.append(SEP)
        header = f"🪙 <b>{asset}</b> — ${s['current']:,.2f}"
        if total_value > 0 and s["current"]:
            lines.append(f"{header} · {s['value'] / total_value * 100:.1f}% da carteira")
        else:
            lines.append(header)
        for r in [x for x in rows if x["asset"] == asset]:
            line = (f"#{r['id']} COMPRA {r['quantity']:g} @ ${r['price']:,.2f}")
            if s["current"]:
                gain = (s["current"] - r["price"]) * r["quantity"]
                pct = (s["current"] - r["price"]) / r["price"] * 100
                line += f"  {_trend_emoji(pct)} ${gain:+,.2f} ({pct:+.1f}%)"
            lines.append(line)
        lines.append(f"📊 Média ${s['avg']:,.2f} · Aberto: {s['qty']:g} {asset}")
        if s["current"]:
            pnl = s["value"] - s["invested"]
            lines.append(f"📈 ${s['value']:,.2f} (investido ${s['invested']:,.2f})  "
                         f"<b>${pnl:+,.2f} ({s['pct']:+.1f}%)</b> {_trend_emoji(pnl)}")
        else:
            lines.append(f"📈 Investido ${s['invested']:,.2f} (sem cotação atual)")
    return "\n".join(lines)


def format_historico(rows: list[dict], matches_by_sell: dict,
                     realized: dict | None = None) -> str:
    """Realized sales with per-lot PnL."""
    realized = realized or {}
    if not rows:
        return "📜 HISTÓRICO · vendas realizadas\n\n📭 Nenhuma venda registrada."
    lines = ["<b>📜 HISTÓRICO</b> · vendas realizadas"]
    total = sum(pnl for pnl, _ in realized.values())
    if realized:
        lines.append("")
        lines.append(f"🏁 PnL realizado total: <b>${total:+,.2f}</b> {_trend_emoji(total)}")
    for asset in sorted({r["asset"] for r in rows}):
        lines.append(SEP)
        lines.append(f"💰 <b>{asset}</b>")
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


def format_help() -> str:
    return (
        "🤖 COMANDOS DO PORTFÓLIO\n"
        "\n🛒 /compra MOEDA,HH:MM,QTD\n"
        "Registra uma compra.\n"
        "Ex: /compra BTC,14:30,0.05\n"
        "\n💸 /venda MOEDA,HH:MM,QTD\n"
        "Registra uma venda (FIFO).\n"
        "Ex: /venda BTC,09:00,0.02\n"
        "\n🔄 /troca DE,PARA,HH:MM,QTD\n"
        "Troca um ativo por outro.\n"
        "Ex: /troca NEAR,ETH,13:50,70.5\n"
        "\n📅 /old_compra MOEDA,DD-MM-AAAA-HH:MM,QTD\n"
        "Compra antiga.\n"
        "Ex: /old_compra BTC,30-12-2025-14:54,0.1\n"
        "\n📅 /old_venda MOEDA,DD-MM-AAAA-HH:MM,QTD\n"
        "Venda antiga.\n"
        "Ex: /old_venda BTC,15-01-2026-10:00,0.05\n"
        "\n📅 /old_troca DE,PARA,DD-MM-AAAA-HH:MM,QTD\n"
        "Troca antiga.\n"
        "Ex: /old_troca NEAR,ETH,15-01-2026-13:50,70.5\n"
        "\n📋 /extrato [MOEDA]\n"
        "Posições em aberto + % vs cotação atual.\n"
        "Ex: /extrato BTC\n"
        "\n📜 /historico [MOEDA]\n"
        "Vendas realizadas + PnL.\n"
        "Ex: /historico ETH\n"
        "\n✏️ /edit ID,CAMPO,VALOR\n"
        "Edita qtd, preco ou hora (HH:MM ou data completa).\n"
        "Ex: /edit 3,preco,65000\n"
        "\n🗑️ /delete ID\n"
        "Apaga um registro e recalcula o FIFO.\n"
        "Ex: /delete 3"
    )


def send_telegram(bot_token: str, chat_id: str, text: str, dry_run: bool = True) -> bool:
    if dry_run:
        log.info("[DRY-RUN] Telegram message suppressed:\n%s", text)
        return True
    if not bot_token or not chat_id:
        log.error("Telegram credentials missing; alert NOT sent")
        return False
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    r = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json=payload,
        timeout=15,
    )
    if r.status_code == 400 and "can't parse" in r.text:
        # HTML malformado (ex: texto com < > vindo de input do usuário):
        # reenvia como texto puro em vez de perder a mensagem.
        log.warning("Telegram HTML parse failed, retrying as plain text")
        payload.pop("parse_mode")
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=15,
        )
    if r.status_code != 200:
        log.error("Telegram send failed: %s %s", r.status_code, r.text[:200])
        return False
    return True
