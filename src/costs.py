"""Fees + slippage: applied against the trader on both fills."""


def apply_entry(price: float, cfg: dict) -> float:
    b = cfg["backtest"]
    return price * (1 + (b["fee_percent"] + b["slippage_percent"]) / 100)


def apply_exit(price: float, cfg: dict) -> float:
    b = cfg["backtest"]
    return price * (1 - (b["fee_percent"] + b["slippage_percent"]) / 100)
