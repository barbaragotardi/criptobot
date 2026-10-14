"""Telegram alert template."""

import logging
from html import escape as _esc

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


def fmt_qty(qty: float) -> str:
    """Format quantity without scientific notation (1e-08 -> 0.00000001).

    Trims trailing zeros, up to 8 decimals. Dust (<1e-9) shows as '0'.
    """
    try:
        q = float(qty)
    except (TypeError, ValueError):
        return "0"
    if abs(q) < 1e-9:
        return "0"
    s = f"{q:.8f}".rstrip("0").rstrip(".")
    return s if s else "0"


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
        f"🔢 Quantidade: {fmt_qty(qty)}\n"
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
        f"🔢 Quantidade: {fmt_qty(qty)}\n"
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
            f"{_trend_emoji(m['pnl_pct'])} {fmt_qty(m['qty'])} @ ${m['buy_price']:,.2f} "
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
        f"\n💸 Vendeu: {fmt_qty(qty_from)} {asset_from} @ ${price_from:,.2f} "
        f"(${qty_from * price_from:,.2f})",
        f"🛒 Comprou: {fmt_qty(qty_to)} {asset_to} @ ${price_to:,.2f} "
        f"(${qty_to * price_to:,.2f})"
        f"{when_line}"
        f"{extra}",
        f"\n📦 Lotes {asset_from} abatidos (FIFO):",
    ]
    total_pnl = 0.0
    for m in matches:
        total_pnl += m["pnl_usd"]
        lines.append(
            f"{_trend_emoji(m['pnl_pct'])} {fmt_qty(m['qty'])} @ ${m['buy_price']:,.2f} "
            f"→ PnL: ${m['pnl_usd']:+,.2f} ({m['pnl_pct']:+.1f}%)"
        )
    lines.append(f"\n🏁 PnL realizado nesta troca: ${total_pnl:+,.2f} {_trend_emoji(total_pnl)}")
    return "\n".join(lines)


SEP = "➖➖➖➖➖➖➖➖"


def format_extrato(rows: list[dict], avgs: dict, prices: dict) -> str:
    """Open BUY positions: portfolio summary + per-asset blocks with allocation."""
    # Hide float dust: lots with remaining <= EPS don't count as open.
    EPS = 1e-9
    rows = [r for r in rows
            if r.get("side", "BUY") == "BUY" and (r.get("remaining_qty") or 0) > EPS]
    # Drop dust-only averages (qty <= EPS) so a fully-sold asset disappears.
    avgs = {k: v for k, v in (avgs or {}).items() if (v[1] or 0) > EPS}
    assets = sorted({r["asset"] for r in rows if (r["asset"], "BUY") in avgs})
    if not assets:
        return "📋 EXTRATO · posições em aberto\n\n📭 Nenhuma posição em aberto."
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
        lines.append("")
        lines.append("🏆 <b>Ranking</b> · melhor → pior")
        for i, (a, p) in enumerate(
                sorted(ranked, key=lambda x: x[1], reverse=True), 1):
            lines.append(f"{i}. <b>{a}</b> {p:+.1f}% {_trend_emoji(p)}")

    for asset in assets:
        s = stats[asset]
        lines.append(SEP)
        header = f"🪙 <b>{asset}</b> — ${s['current']:,.2f}"
        if total_value > 0 and s["current"]:
            lines.append(f"{header} · {s['value'] / total_value * 100:.1f}% da carteira")
        else:
            lines.append(header)
        for r in [x for x in rows if x["asset"] == asset]:
            open_q = r.get("remaining_qty") or r.get("quantity") or 0
            line = (f"#{r['id']} COMPRA {fmt_qty(open_q)} @ ${r['price']:,.2f}")
            if s["current"]:
                gain = (s["current"] - r["price"]) * open_q
                pct = (s["current"] - r["price"]) / r["price"] * 100
                line += f"  {_trend_emoji(pct)} ${gain:+,.2f} ({pct:+.1f}%)"
            lines.append(line)
        lines.append(f"📊 Média ${s['avg']:,.2f} · Aberto: {fmt_qty(s['qty'])} {asset}")
        if s["current"] and s["pct"] is not None:
            pnl = s["value"] - s["invested"]
            lines.append(f"📈 ${s['value']:,.2f} (investido ${s['invested']:,.2f})  "
                         f"<b>${pnl:+,.2f} ({s['pct']:+.1f}%)</b> {_trend_emoji(pnl)}")
        elif s["current"]:
            lines.append(f"📈 ${s['value']:,.2f} (investido ${s['invested']:,.2f})")
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
                f"#{r['id']} VENDA {fmt_qty(r['quantity'])} @ ${r['price']:,.2f} "
                f"(${r['cost_usd']:,.2f}) {_trend_emoji(sell_pnl)}"
            )
            for m in sell_matches:
                lines.append(
                    f"  ↳ lote #{m['buy_trade_id']}: {fmt_qty(m['qty'])} "
                    f"@ ${m['buy_price']:,.2f} "
                    f"→ PnL: ${m['pnl_usd']:+,.2f} ({m['pnl_pct']:+.1f}%) "
                    f"{_trend_emoji(m['pnl_pct'])}"
                )
        if asset in realized:
            pnl, matched = realized[asset]
            lines.append(f"🏁 PnL realizado: ${pnl:+,.2f} (qtd vendida {fmt_qty(matched)}) "
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
        f"\n🪙 #{trade['id']} {op} {fmt_qty(trade['quantity'])} {trade['asset']} "
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
        "Registra uma venda (FIFO). Use 'all' para vender tudo.\n"
        "Ex: /venda BTC,09:00,0.02 ou /venda BTC,09:00,all\n"
        "\n🔄 /troca DE,PARA,HH:MM,QTD\n"
        "Troca um ativo por outro. Use 'all' para trocar tudo.\n"
        "Ex: /troca NEAR,ETH,13:50,70.5\n"
        "\n📅 /old_compra MOEDA,DD-MM-AAAA-HH:MM,QTD\n"
        "Compra antiga.\n"
        "Ex: /old_compra BTC,30-12-2025-14:54,0.1\n"
        "\n📅 /old_venda MOEDA,DD-MM-AAAA-HH:MM,QTD\n"
        "Venda antiga. Use 'all' para vender tudo.\n"
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
        "Ex: /delete 3\n"
        "\n🛡️ /suportes MOEDA\n"
        "Suportes (MM30/pivot/Fib).\n"
        "Ex: /suportes BTC\n"
        "\n📰 /dossier MOEDA [dias]\n"
        "Notícias recentes (até 30d).\n"
        "Ex: /dossier SOL 7\n"
        "\n🔍 /analyze MOEDA\n"
        "Por que o motor observa (ou não) o ativo.\n"
        "Ex: /analyze SOL"
    )


def format_suportes(asset: str, s: dict) -> str:
    """Compact support levels (MA30/pivot/Fib + confluence zone)."""
    p = s.get("params", {})
    n_short, n_long = p.get("sma_short", 30), p.get("sma_long", 200)
    pivot, fib, swing = s["pivot"], s["fib"], s["swing"]
    lo, hi = s["zone"]
    lines = [f"🛡️ SUPORTES {asset} — ${s['current']:,.2f}", ""]
    if lo and hi:
        lines.append(f"Zona imediata: ${lo:,.0f}–${hi:,.0f}")
    if s.get("sma_short"):
        lines.append(f"MM{n_short}: ${s['sma_short']:,.2f}")
    if s.get("ema_short"):
        lines.append(f"EMA{n_short}: ${s['ema_short']:,.2f}")
    lines.append(f"Pivot: ${pivot['p']:,.2f} · S1 ${pivot['s1']:,.2f} · S2 ${pivot['s2']:,.2f}")
    for r in sorted(fib):
        lines.append(f"Fib {r * 100:.1f}%: ${fib[r]:,.2f}")
    if s.get("sma_long"):
        lines.append(f"MM{n_long} (tendência): ${s['sma_long']:,.2f}")
    lines.append(f"Swing: ${swing['low']:,.2f} em {swing['low_date'][:10]} → "
                 f"${swing['high']:,.2f} em {swing['high_date'][:10]}")
    if swing.get("fallback"):
        lines.append("⚠️ sem perna clara, usando extremos 90d.")
    lines.append("\n⚠️ Referência técnica, não garantia.")
    return "\n".join(lines)


TOPIC_LABELS = {
    "regulation": "regulação", "etf_flows": "fluxos de ETF",
    "hack_exploit": "hack/exploit", "macro_rates": "macro/juros",
    "exchange_listing": "listagem em exchange", "partnership": "parceria",
    "protocol_upgrade": "upgrade de protocolo", "liquidations": "liquidações",
    "adoption": "adoção", "legal": "jurídico", "whale_activity": "baleias",
    "other": "outros",
}

RISK_FLAG_LABELS = {
    "many_open_positions": "muitas posições abertas",
    "high_correlation": "alta correlação",
    "already_holding_paper": "já com posição paper no ativo",
    "already_holding_manual": "já em carteira manual",
    "near_exposure_cap": "próximo do teto de exposição",
}

BLOCKER_LABELS = {
    "market_bearish": "mercado em viés de baixa",
    "macro_fail": "macro reprovado",
    "no_pullback": "sem pullback válido",
    "cooldown_active": "em cooldown",
    "awaiting_confirmation": "aguardando confirmação",
    "exposure_blocked": "bloqueado por exposição",
    "rr_below_min": "retorno/risco abaixo do mínimo",
    "tp_below_min": "alvo abaixo do mínimo",
}

WATCHER_LABELS = {
    "near_ema20": "próximo da EMA20",
    "near_ema50": "próximo da EMA50",
    "awaiting_confirmation": "aguardando confirmação",
    "near_support": "próximo de suporte",
}


def format_council(res: dict) -> str:
    """Follow-up briefing. Numbers come from code facts only, never from the LLM."""
    b = (res.get("briefing") or {})
    n = (res.get("news") or {})
    r = (res.get("risk") or {})
    setup = res.get("setup", {})
    lines = [f"🧠 Contexto IA · {_esc(str(res.get('asset', '')))} (não é recomendação)", ""]
    tone = {"supportive": "tom: sem alertas adicionais", "neutral": "tom: neutro",
            "caution": "tom: cautela"}.get(b.get("tone", "neutral"), "")
    if tone:
        lines.append(tone)
    for x in (b.get("bullets") or [])[:6]:
        lines.append(f"• {_esc(str(x))}")
    if n.get("sentiment") and n.get("sentiment") != "neutral":
        lines.append(f"Notícias: {_esc(str(n['sentiment']))} (confiança {_esc(str(n.get('confidence', 'low')))})")
    for x in (n.get("catalysts") or [])[:5]:
        if x in TOPIC_LABELS:
            lines.append(f"• {_esc(TOPIC_LABELS[x])}")
    for x in (n.get("risks") or [])[:5]:
        if x in TOPIC_LABELS:
            lines.append(f"⚠️ {_esc(TOPIC_LABELS[x])}")
    if n.get("rationale"):
        lines.append(f"• {_esc(str(n['rationale']))}")
    if (r.get("concentration")) in ("high", "medium"):
        lines.append(f"Concentração: {_esc(str(r['concentration']))}")
    for x in (r.get("flags") or [])[:5]:
        if x in RISK_FLAG_LABELS:
            lines.append(f"• {_esc(RISK_FLAG_LABELS[x])}")
    if setup.get("news_mode") == "sql":
        lines.append("(busca vetorial indisponível; fallback por palavra-chave)")
    lines.append("\n⚠️ Contexto gerado por IA, pode errar. Decisão é sua.")
    return "\n".join(lines)


def format_dossier(asset: str, snippets: list[dict], mode: str, days: int) -> str:
    if not snippets:
        return f"📰 DOSSIÊ {_esc(asset)} · {days}d\n\n📭 Sem notícias relevantes no período."
    lines = [f"📰 DOSSIÊ {_esc(asset)} · {days}d ({_esc(mode)})", ""]
    for s in snippets[:10]:
        lines.append(f"• {_esc(s['title'])} ({_esc(s['source'])})")
    lines.append("\n⚠️ Resumo de notícias, não recomendação.")
    return "\n".join(lines)


def format_diagnosis(asset: str, facts: str, narrative) -> str:
    lines = [f"🔍 ANÁLISE {_esc(asset)}", "", f"Técnico: {_esc(facts)}"]
    if narrative is not None:
        blockers = getattr(narrative, "blockers", None)
        if blockers is None and isinstance(narrative, dict):
            blockers = narrative.get("blockers")
        for x in (blockers or [])[:5]:
            lines.append(f"⛔ {_esc(BLOCKER_LABELS.get(str(x), str(x)))}")
        watchers = getattr(narrative, "watchers", None)
        if watchers is None and isinstance(narrative, dict):
            watchers = narrative.get("watchers")
        for x in (watchers or [])[:5]:
            lines.append(f"👀 {_esc(WATCHER_LABELS.get(str(x), str(x)))}")
    lines.append("\n⚠️ Leitura técnica + IA, não recomendação.")
    return "\n".join(lines)


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
