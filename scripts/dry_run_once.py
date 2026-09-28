"""Single dry-run cycle against Binance (read-only). Forces dry_run=True."""

import logging
import sys

sys.path.insert(0, ".")

from src.config import load_config
from src.engine.cycle import run_cycle
from src.logging_config import setup_logging
from src.setup.state import connect

setup_logging()
logging.getLogger().setLevel(logging.INFO)

cfg = load_config()
cfg["system"]["dry_run"] = True
conn = connect(cfg["system"]["db_path"])
results = run_cycle(cfg, conn)
print("RESULTS:", results)
