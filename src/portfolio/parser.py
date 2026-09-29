"""Parse /compra and /venda commands. Format: /compra MOEDA,HH:MM,QUANTIDADE."""

import logging
import re

log = logging.getLogger(__name__)

COMMAND_RE = re.compile(
    r"^/(compra|venda)\s+([A-Za-z0-9]+)\s*,\s*(\d{1,2}:\d{2})\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE,
)


def parse_command(text: str) -> tuple[str, str, str, float]:
    """Return (side, asset, hhmm, qty). side is 'BUY' or 'SELL'. Raises ValueError."""
    m = COMMAND_RE.match((text or "").strip())
    if not m:
        raise ValueError(
            "Formato inválido. Use: /compra MOEDA,HH:MM,QUANTIDADE "
            "(ex: /compra BTC,14:30,0.05)"
        )
    side = "BUY" if m.group(1).lower() == "compra" else "SELL"
    asset = m.group(2).upper()
    hhmm = m.group(3)
    qty = float(m.group(4))
    if qty <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    hh, mm = int(hhmm.split(":")[0]), int(hhmm.split(":")[1])
    if hh > 23 or mm > 59:
        raise ValueError(f"Horário inválido: {hhmm}.")
    return side, asset, hhmm, qty


def validate_asset(asset: str, cfg: dict) -> None:
    """Raise ValueError if asset is not in the monitored list."""
    if asset not in cfg["assets"]:
        raise ValueError(
            f"Moeda {asset} não monitorada. "
            f"Válidas: {', '.join(cfg['assets'])}."
        )
