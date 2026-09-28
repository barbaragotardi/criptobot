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
