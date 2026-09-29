"""Paper trading performance report (V4): closed positions -> section-31 metrics."""

import sys

sys.path.insert(0, ".")

from src.backtest.metrics import breakdown, summarize
from src.config import load_config
from src.paper.store import list_closed, list_open
from src.setup.state import connect

cfg = load_config()
conn = connect(cfg["system"]["db_path"])

closed = list_closed(conn)
print(f"CLOSED: {len(closed)}")
if closed:
    print(summarize(closed))
    print("BY ASSET:", breakdown(closed, "asset"))

open_pos = list_open(conn)
print(f"OPEN: {len(open_pos)}")
for p in open_pos:
    print(f"  {p['asset']} entry={p['entry']:.2f} stop={p['stop']:.2f} tp={p['tp']:.2f}")
