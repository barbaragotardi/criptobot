"""Sanity checks reproducing project.md numeric examples (sections 20, 22)."""

import sys

sys.path.insert(0, ".")

from src.risk.engine import calc_stop, calc_tp, position_size, risk_reward

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        failures.append(name)


# Section 20: Entry 100, Stop 94, TP 106 -> R/R 1.0 -> must be rejected (< 2.0)
rr = risk_reward(100, 94, 106)
check("R/R example = 1.0", abs(rr - 1.0) < 1e-9)
check("R/R 1.0 rejected (min 2.0)", rr < 2.0)

# Passing case: Entry 100, Stop 97, TP 106 -> R/R 2.0 -> accepted
rr2 = risk_reward(100, 97, 106)
check("R/R 2.0 accepted", rr2 >= 2.0 - 1e-9)

# Section 17: stop = pullback_low - ATR*K
check("stop = 95 - 2*1.0 = 93", calc_stop(95, 2.0, 1.0) == 93.0)

# Section 22: balance 1000, risk 1%, entry 100, stop 95 -> position $200, risk $10
pos, risk_usd = position_size(1000, 1.0, 100, 95)
check("position size = $200", abs(pos - 200) < 1e-9)
check("capital at risk = $10", abs(risk_usd - 10) < 1e-9)

# Section 19: TP classification
cfg = {"target": {"absolute_min_percent": 3.0, "preferred_min_percent": 5.0, "preferred_max_percent": 10.0}}
_, cls = calc_tp(100, 106, cfg)
check("6% -> FAIXA PREFERENCIAL", cls == "FAIXA PREFERENCIAL")
_, cls2 = calc_tp(100, 104, cfg)
check("4% -> ABAIXO DA FAIXA PREFERENCIAL", cls2 == "ABAIXO DA FAIXA PREFERENCIAL")
_, cls3 = calc_tp(100, 102, cfg)
check("2% -> REJECT", cls3 == "REJECT")

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("All sanity checks passed.")
