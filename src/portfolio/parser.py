"""Parse /compra and /venda commands. Format: /compra MOEDA,HH:MM,QUANTIDADE."""

import logging
import re

log = logging.getLogger(__name__)

COMMAND_RE = re.compile(
    r"^/(compra|venda)\s+([A-Za-z0-9]+)\s*,\s*(\d{1,2}:\d{2})\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE,
)

EDIT_RE = re.compile(
    r"^/edit\s+(\d+)\s*,\s*([A-Za-z\xc0-\xff]+)\s*,\s*(\S+)\s*$",
    re.IGNORECASE,
)

DELETE_RE = re.compile(r"^/delete\s+(\d+)\s*$", re.IGNORECASE)

TROCA_RE = re.compile(
    r"^/troca\s+([A-Za-z0-9]+)\s*,\s*([A-Za-z0-9]+)\s*,\s*(\d{1,2}:\d{2})\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE,
)

OLD_COMMAND_RE = re.compile(
    r"^/old_(compra|venda)\s+([A-Za-z0-9]+)\s*,\s*(\d{1,2}-\d{1,2}-\d{4}-\d{1,2}:\d{2})\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE,
)

OLD_TROCA_RE = re.compile(
    r"^/old_troca\s+([A-Za-z0-9]+)\s*,\s*([A-Za-z0-9]+)\s*,\s*(\d{1,2}-\d{1,2}-\d{4}-\d{1,2}:\d{2})\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*$",
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


def parse_edit(text: str) -> tuple[int, str, str]:
    """Return (trade_id, field, raw_value). field is 'QTY', 'PRICE' or 'TIME'.

    Value validation is per-field (numeric > 0 for QTY/PRICE, HH:MM for TIME).
    Raises ValueError.
    """
    m = EDIT_RE.match((text or "").strip())
    if not m:
        raise ValueError(
            "Formato inválido. Use: /edit ID,CAMPO,NOVO_VALOR "
            "(ex: /edit 3,qtd,0.1 | /edit 3,preco,65000 | /edit 3,hora,14:30 "
            "ou /edit 3,hora,30-12-2025-14:54)"
        )
    field = m.group(2).lower().replace("ç", "c").replace("ê", "e")
    if field in ("qtd", "quantidade", "qty", "quantity"):
        norm = "QTY"
    elif field in ("preco", "price", "valor"):
        norm = "PRICE"
    elif field in ("hora", "horario", "time"):
        norm = "TIME"
    else:
        raise ValueError(
            f"Campo inválido: {m.group(2)}. Use qtd, preco ou hora."
        )
    raw = m.group(3)
    if norm in ("QTY", "PRICE"):
        try:
            val = float(raw.replace(",", "."))
        except ValueError:
            raise ValueError(f"Valor inválido para {norm.lower()}: {raw}.")
        if val <= 0:
            raise ValueError("Valor deve ser maior que zero.")
    else:
        if "-" in raw:
            dt = parse_full_dt(raw)
            raw = dt.strftime("%d-%m-%Y-%H:%M")
        else:
            raw = _validate_hhmm(raw)
    return int(m.group(1)), norm, raw


def parse_delete(text: str) -> int:
    """Return trade_id. Raises ValueError."""
    m = DELETE_RE.match((text or "").strip())
    if not m:
        raise ValueError("Formato inválido. Use: /delete ID (ex: /delete 3)")
    return int(m.group(1))


def _validate_hhmm(hhmm: str) -> str:
    parts = hhmm.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"Horário inválido: {hhmm}. Use HH:MM.")
    hh, mm = int(parts[0]), int(parts[1])
    if hh > 23 or mm > 59:
        raise ValueError(f"Horário inválido: {hhmm}.")
    return f"{hh:02d}:{mm:02d}"


def _validate_qty(raw: str) -> float:
    try:
        qty = float(raw.replace(",", "."))
    except ValueError:
        raise ValueError(f"Quantidade inválida: {raw}.")
    if qty <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    return qty


def parse_troca(text: str) -> tuple[str, str, str, float]:
    """Return (asset_from, asset_to, hhmm, qty). Raises ValueError."""
    m = TROCA_RE.match((text or "").strip())
    if not m:
        raise ValueError(
            "Formato inválido. Use: /troca DE,PARA,HH:MM,QUANTIDADE "
            "(ex: /troca NEAR,ETH,13:50,70.5)"
        )
    asset_from, asset_to = m.group(1).upper(), m.group(2).upper()
    if asset_from == asset_to:
        raise ValueError("Troca precisa de dois ativos diferentes.")
    return asset_from, asset_to, _validate_hhmm(m.group(3)), _validate_qty(m.group(4))


def parse_full_dt(raw: str):
    """Return naive datetime from DD-MM-AAAA-HH:MM. Raises ValueError."""
    from datetime import datetime
    try:
        dd, mm, yyyy, hhmm = raw.split("-")
        hh, mi = hhmm.split(":")
        return datetime(int(yyyy), int(mm), int(dd), int(hh), int(mi))
    except (ValueError, IndexError):
        raise ValueError(
            f"Data inválida: {raw}. Use DD-MM-AAAA-HH:MM "
            "(ex: 30-12-2025-14:54)."
        )


def parse_old_command(text: str) -> tuple[str, str, object, float]:
    """Return (side, asset, naive datetime, qty) for /old_compra|/old_venda."""
    m = OLD_COMMAND_RE.match((text or "").strip())
    if not m:
        raise ValueError(
            "Formato inválido. Use: /old_compra MOEDA,DD-MM-AAAA-HH:MM,QUANTIDADE "
            "(ex: /old_compra BTC,30-12-2025-14:54,0.1)"
        )
    side = "BUY" if m.group(1).lower() == "compra" else "SELL"
    return side, m.group(2).upper(), parse_full_dt(m.group(3)), _validate_qty(m.group(4))


def parse_old_troca(text: str) -> tuple[str, str, object, float]:
    """Return (asset_from, asset_to, naive datetime, qty). Raises ValueError."""
    m = OLD_TROCA_RE.match((text or "").strip())
    if not m:
        raise ValueError(
            "Formato inválido. Use: /old_troca DE,PARA,DD-MM-AAAA-HH:MM,QUANTIDADE "
            "(ex: /old_troca NEAR,ETH,15-01-2026-13:50,70.5)"
        )
    asset_from, asset_to = m.group(1).upper(), m.group(2).upper()
    if asset_from == asset_to:
        raise ValueError("Troca precisa de dois ativos diferentes.")
    return asset_from, asset_to, parse_full_dt(m.group(3)), _validate_qty(m.group(4))
