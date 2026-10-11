"""Paper trading performance report (V4): closed/open positions."""

import sys

sys.path.insert(0, ".")

from src.config import load_config
from src.paper.store import list_closed, list_open
from src.strategy.state import connect

cfg = load_config()
conn = connect(cfg["system"]["db_path"])

closed = list_closed(conn)
print(f"CLOSED: {len(closed)}")
for p in closed:
    print(f"  {p['asset']} entry={p['entry']:.2f} exit={p['exit_price']:.2f} "
          f"pnl={p['pnl_pct']:+.2f}% (${p['pnl_usd']:+.2f}) [{p['exit_reason']}]")

open_pos = list_open(conn)
print(f"OPEN: {len(open_pos)}")
for p in open_pos:
    print(f"  {p['asset']} entry={p['entry']:.2f} stop={p['stop']:.2f} tp={p['tp']:.2f}")
