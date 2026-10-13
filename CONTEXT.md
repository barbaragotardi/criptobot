# CONTEXT.md — Robit

## Overview
- Monitor crypto assets for spot swing-trade pullback setups and send Telegram alerts.
- Never execute orders automatically. User decides and trades manually on exchange.
- Pipeline per asset per cycle: Market Filter BTC (1x per cycle) -> macro filter 1D -> pullback 4H (EMA20/EMA50 touch) -> WATCHING -> confirmation 15m (closed candles only) -> stop (pullback_low - ATR*K) -> resistance (max 50x 4H) -> TP -> validate min return >=3% -> validate R/R >=2.0 -> exposure check -> sizing -> Telegram alert -> paper open.
- If any mandatory step fails: return NO_TRADE / NO_SETUP / REJECTED, send no alert.
- Include paper trading (virtual ledger, auto-open on SIGNAL, monitor TP/STOP on 15m closed candles) and manual portfolio via Telegram (/compra /venda /troca /old_* /extrato /historico /edit /delete /help).
- Spec source of truth: `project.md`. Architecture map: `doc/ARCHITECTURE.md`. Runtime behavior: `README.md`.

## Tech Stack
- Python 3.12 (`python = ^3.12` in `pyproject.toml`)
- Poetry + poetry-core (only package manager; `poetry.lock` committed)
- Exchange: `ccxt ^4.5.84` against Binance, read-only (`fetch_ohlcv`, `fetch_ticker`); quote `USDT`
- DB: Postgres 16-alpine via `psycopg ^3.2` (binary); connection only via `$DATABASE_URL`; tables: `asset_state`, `daily_signals`, `paper_positions`, `portfolio_trades`, `portfolio_alert_state`, `telegram_offset`
- Libs: `pandas ^3.0.6`, `numpy ^2.5.3`, `pyyaml ^6.0.3`, `python-dotenv ^1.2.3`, `requests ^2.34.2`
- Market data providers: CoinGecko, CoinMarketCap, CoinPaprika (under `src/market/providers/`), plus news classifier (`src/market/news/`)
- Alerts: Telegram Bot API via `getUpdates` long-poll (`telegram_poll_timeout_s: 30`); no webhook framework
- Runtime: Docker Compose (`db` + `app`), `./config:/app/config:ro`; local run via `poetry run python main.py`
- Config: `config/config.yaml` + `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DATABASE_URL`, `POSTGRES_*`); timezone `America/Sao_Paulo`
- Scripts: `scripts/sanity_check.py`, `scripts/dry_run_once.py`, `scripts/paper_report.py`
- No test framework / linter configured in V1 (verify via scripts above).

## Repository Structure
- `main.py`: continuous loop; poll for new closed 15m candle (`wait_for_new_candle`), then `run_cycle` + `check_open_positions` + `check_portfolio_alerts`; starts `telegram-listener` daemon thread if `portfolio.enabled`.
- `config/config.yaml`: all strategy params (assets, timeframes, warmup, EMA, ATR, macro, market_filter, entry, confirmation, invalidation, risk, target, exposure, paper_trading, portfolio, system). Mirror of `project.md` §33.
- `src/config/`: `load_config`, `setup_logging` (log format `[INFO] ...` per `project.md` §37).
- `src/exchange/client.py`: `make_exchange`, `symbol_for`, `fetch_ohlcv` / `fetch_warmup`; always discard last (open) candle.
- `src/strategy/`: `indicators.py` (EMA20/50/100/200, ATR14), `filters.py` (`evaluate_market_filter`, `macro_pass`), `pullback.py` (`detect_pullback`), `risk.py` (`calc_stop_method`, `find_resistance`, `calc_tp`, `risk_reward`, `position_size`), `cycle.py` (`evaluate_asset`, `run_cycle`), `state.py` (Postgres state machine + cooldown).
- `src/confirmation/confirm.py`: methods `reversal | ema_reclaim | any`; closed candles only.
- `src/market/providers/`: `coingecko/`, `coinmktcap/`, `coinpaprika/` (price snapshot, fallback chain); `src/market/news/`: news + AI classification.
- `src/exposure/manager.py`: `exposure_ok`, `record_signal`; V4 counts `paper_positions OPEN`, not WATCHING.
- `src/paper/`: `store.py` (open/close/list/count, entry with costs via `apply_entry`, 1 OPEN per asset dedup), `monitor.py` (`check_open_positions`; STOP wins tie in same candle; no timeout).
- `src/portfolio/`: `parser.py`, `pricing.py` (`price_at` / `price_at_dt` via 1m closed candle), `store.py` (FIFO with `commit` flag + `recompute_fifo`), `listener.py` (`run_listener`), `monitor.py` (`check_portfolio_alerts` 5%/10% with hysteresis).
- `src/alerts/telegram.py`: alert template (§28), `format_paper_open/close`, portfolio formatters, `get_updates`, send (honor `dry_run`).
- `src/costs.py`, `src/db.py`: fee/slippage (`backtest.fee_percent 0.1`, `slippage 0.05`) and DB helpers.
- `doc/ARCHITECTURE.md`: module map, V4/V5 notes, confusing points (injectable clock, non-persisted states).
- `project.md`: full strategy spec (39 sections); `README.md`: status table (`SIGNAL|WATCHING|NO_SETUP|NO_TRADE|REJECTED|INVALIDATED|TIMEOUT|COOLDOWN|SEND_FAILED|ERROR`) and manual verification.
- `compose.yaml`, `Dockerfile`, `.env.example`, `scripts/`, `data/` (local, do not version run outputs).

## Coding Rules (Crucial)
- Use Poetry exclusively. Run `poetry install`, `poetry run python main.py`, `poetry run python scripts/sanity_check.py`, `poetry run python scripts/dry_run_once.py`. Do not suggest `pip install`, `pip`, `conda`, or `npm`.
- Do not hardcode strategy params. Read everything from `config/config.yaml` via `load_config` (assets, EMAs, ATR period 14, touch_threshold 1.0%, atr_k 0.5, R/R 2.0, min 3% / preferred 5-10% / max_tp 50%, cooldown 12h, max_15m 16, exposure caps). `preferred_max_percent` is label only; real cap is `max_tp_percent`.
- Compute Market Filter once per cycle and reuse in memory (`cache_per_cycle: true`). Do not query per asset.
- Use only closed candles. `fetch_ohlcv` already excludes open candle; never use `raw[-1]` as signal; confirmation requires `candle_closed_only: true`.
- Follow pipeline order in `src/strategy/cycle.py:evaluate_asset` (§5). Do not reorder Entry->Stop->Resistance->TP->return->R/R. Do not tighten Stop to meet R/R; discard trade instead.
- Persist state correctly: states `TOUCHED_EMA`/`CONFIRMED`/`COOLDOWN` are intra-cycle only, never write to DB. `REJECTED` does not exit WATCHING; exit only via TIMEOUT/invalidation/macro fail. `INVALIDATED` -> `NO_SETUP` next cycle; `ALERT_SENT` -> `NO_SETUP` after `cooldown_until_ts` expiry.
- Accept injectable clock: `evaluate_asset(..., now_ts)`, `exposure_ok/record_signal(..., now)`; production passes `None` (wall clock); tests inject epoch seconds (convert candle ms -> s).
- Respect idempotency: 1 paper OPEN per asset; `/venda` larger than open position is rejected with no write; `/edit`/`/delete`/`/old_*` use `recompute_fifo` with full rollback on `ValueError`; reject future dates.
- Validate Telegram input: only assets listed in `config.yaml` and only `TELEGRAM_CHAT_ID`; use existing parsers in `src/portfolio/parser.py`.
- Match existing style: stdlib + listed deps only; no new exchange writes (read-only `ccxt`); no new DB tables without migration in `src/strategy/state.py` / `src/paper/store.py` / `src/portfolio/store.py`; keep `[INFO]` log prefixes.
- Require `$DATABASE_URL`; if empty, fail fast with error. Do not add SQLite fallback.
