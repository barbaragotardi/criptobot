"""Fixed chronological splits. No arbitrary dates: prevents accidental peeking."""

import datetime

SPLITS = {
    "dev": ("2023-03-01", "2024-09-01"),
    "validation": ("2024-09-01", "2025-09-01"),
    "test": ("2025-09-01", "2026-09-28"),
}


def to_ms(s: str) -> int:
    dt = datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def split_range(name: str) -> tuple[int, int]:
    start, end = SPLITS[name]
    return to_ms(start), to_ms(end)
