"""Parameter grid: deep-merge overrides onto a base cfg."""

import copy
import itertools


def apply_overrides(cfg: dict, overrides: dict) -> dict:
    out = copy.deepcopy(cfg)
    for dotted, value in overrides.items():
        node = out
        *path, last = dotted.split(".")
        for p in path:
            node = node[p]
        node[last] = value
    return out


def expand(grid: dict[str, list]) -> list[dict]:
    """grid: {'risk.min_risk_reward': [1.0, 1.5, 2.0]} -> list of override dicts."""
    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(grid[k] for k in keys))]
