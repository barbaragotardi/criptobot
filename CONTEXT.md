# CONTEXT.md — Robit

## Overview
- Monitor crypto assets for spot swing-trade pullback setups and send Telegram alerts.
- Never execute orders automatically. User decides and trades manually on exchange.
- Pipeline per asset per cycle: Market Filter BTC (1x per cycle) -> macro filter 1D -> pullback 4H (EMA20/EMA50 touch) -> WATCHING -> confirmation 15m (closed candles only) -> stop (pullback_low - ATR*K) -> resistance (max 50x 4H) -> TP -> validate min return >=3% -> validate R/R >=2.0 -> exposure check -> sizing -> Telegram alert -> paper open.
- If any mandatory step fails: return NO_TRADE / NO_SETUP / REJECTED, send no alert.
- Include paper trading (virtual ledger, auto-open on SIGNAL, monitor TP/STOP on 15m closed candles) and manual portfolio via Telegram (/compra /venda /troca /old_* /extrato /historico /edit /delete /help).
- Include support levels calculator (`src/supports/calc.py`: MA30/EMA30, daily pivot S1/S2, Fibonacci with fractal swing anchors; Telegram `/suportes` command).
- Include AI Trade Council (qualitative layer only): after `SIGNAL` (alert + `ALERT_SENT` unchanged), background thread runs news + risk agents in parallel -> chief briefing -> follow-up "🧠 Contexto IA" via Telegram; persists to `council_reports` + `ai_calls`. Never vetoes signal, never recalculates numbers. Commands `/dossier` (news) and `/analyze` (diagnostic).
- Strategy reference: `README.md` (pipeline, status table). Architecture map: `doc/ARCHITECTURE.md`. AI layer details: `src/ai_agents/README.md`, `src/ai_agents/rag/README.md`.

## Tech Stack
- Python 3.12 (`python = ^3.12` in `pyproject.toml`)
- Poetry + poetry-core (only package manager; `poetry.lock` committed)
- Exchange: `ccxt ^4.5.84` against Binance, read-only (`fetch_ohlcv`, `fetch_ticker`); quote `USDT`
- DB: Postgres 16-alpine via `psycopg ^3.2` (binary) + pgvector `v0.8.0` (custom `Dockerfile.db`; same musl base so `pgdata` stays compatible); connection only via `$DATABASE_URL`; tables: `asset_state`, `daily_signals`, `paper_positions`, `portfolio_trades`, `portfolio_alert_state`, `telegram_offset`, `news_articles`, `council_reports`, `ai_calls`
- Libs: `pandas ^3.0.6`, `numpy ^2.5.3`, `pyyaml ^6.0.3`, `python-dotenv ^1.2.3`, `requests ^2.34.2`, `litellm ^1.65.0`, `pydantic ^2.10.0`, `google-genai ^1.0.0`
- AI models: `anthropic/claude-haiku-4-5-20251001` via LiteLLM (no fallback), `gemini-embedding-2` (`output_dimensionality=768`, `RETRIEVAL_DOCUMENT` on ingest / `RETRIEVAL_QUERY` on search)
- Market data providers: CoinGecko, CoinMarketCap, CoinPaprika (under `src/market/providers/`), plus news classifier (`src/market/news/`)
- Alerts: Telegram Bot API via `getUpdates` long-poll (`telegram_poll_timeout_s: 30`); no webhook framework
- Runtime: Docker Compose (`db` + `app`), `./config:/app/config:ro`; local run via `poetry run python main.py`; shortcuts via `Makefile` (`make up|update|restart-app|sanity|dry-run|paper-report|psql|backup|restore`); `main.py` starts `telegram-listener` daemon (if `portfolio.enabled`) + `news-ingest` daemon (if `ai.enabled` and `ai.rag.enabled`)
- Config: `config/config.yaml` + `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DATABASE_URL`, `POSTGRES_*`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, optional market-provider keys); timezone `America/Sao_Paulo`
- Scripts: `scripts/sanity_check.py`, `scripts/dry_run_once.py`, `scripts/paper_report.py`, `scripts/council_once.py --asset X [--fake]`, `scripts/smoke_ai.py`, `scripts/rag_probe.py ASSET [--days N] [--top K]`, `scripts/ai_report.py`
- No test framework / linter configured (verify via scripts above; use `--fake` for council to avoid API cost).

## Repository Structure
- `main.py`: continuous loop; poll for new closed 15m candle (`wait_for_new_candle`), then `run_cycle` + `check_open_positions` + `check_portfolio_alerts`; starts `telegram-listener` + `news-ingest` (`_news_ingest_loop`: RSS -> `news_articles` every `ai.rag.ingest_interval_min`, min 600s, never raises) daemon threads.
- `config/config.yaml`: all strategy params (assets, timeframes, warmup, EMA, ATR, macro, market_filter, entry, confirmation, invalidation, risk, target, exposure, paper_trading, portfolio, supports, `ai`, system). `ai:` block holds `enabled`, `model`, `timeout_s 40`, `max_tokens 800`, `temperature 0.0`, `max_calls_per_day 50`, `command_cooldown_s 60`, `embedding_model`, `embedding_dim 768`, `rag:` (`enabled`, `news_max_age_hours 48`, `max_headlines 12`, `min_similarity 0.30`, `near_dup_similarity 0.92`, `retention_days 365`, `ingest_interval_min 60`, `max_days_dossier 30`) and `asset_aliases`.
- `src/config/`: `load_config`, `setup_logging` (log format `[INFO] ...`).
- `src/exchange/client.py`: `make_exchange`, `symbol_for`, `fetch_ohlcv` / `fetch_warmup`; always discard last (open) candle.
- `src/strategy/`: `indicators.py` (EMA20/50/100/200, ATR14), `filters.py` (`evaluate_market_filter`, `macro_pass`), `pullback.py` (`detect_pullback`), `risk.py` (`calc_stop_method`, `find_resistance`, `calc_tp`, `risk_reward`, `position_size`), `cycle.py` (`evaluate_asset`, `run_cycle`; on `SIGNAL` calls `council_submit` in background, fail-open), `state.py` (Postgres state machine + cooldown).
- `src/confirmation/confirm.py`: methods `reversal | ema_reclaim | any`; closed candles only.
- `src/supports/calc.py`: support levels (`compute_ma`, `compute_pivot`, fractal swings, Fibonacci); params from `supports:` block (`sma_short 30`, `sma_long 200`, `discovery_lookback 90`, `fib_ratios`, `fractal_k 2`, `min_swing_move_percent 10.0`, `use_wicks true`).
- `src/ai_agents/`: `council.py` (`run_council`, `submit` with own connection + 2-worker pool), `agents.py` (`run_news/run_risk/run_chief/run_diagnostician`, pt-BR prompts), `schemas.py` (`NewsView`, `RiskView`, `Briefing`, `AssetDiagnosis`, `SCHEMA_VERSION=1`), `llm.py` (`complete_structured` via LiteLLM, `log_call`, number guard), `context.py` (`setup_facts`, `portfolio_facts`, `command_allowed`, deterministic facts, no LLM), `diagnose.py` (`diagnose_text` read-only for `/analyze`); `rag/`: `store.py` (`ingest_once`: RSS -> classify -> insert -> batch-embed NULLs in 50s -> prune), `embed.py` (`embed_texts`, `embed_query`), `retrieve.py` (`retrieve` -> `(snippets, mode)`; `vector` cosine with cutoff/dedup/cap, `sql` ILIKE fallback).
- `src/market/providers/`: `coingecko/`, `coinmktcap/`, `coinpaprika/` (price snapshot, fallback chain); `src/market/news/`: news + AI classification.
- `src/exposure/manager.py`: `exposure_ok`, `record_signal`; counts `paper_positions OPEN`, not WATCHING.
- `src/paper/`: `store.py` (open/close/list/count, entry with costs via `apply_entry`, 1 OPEN per asset dedup), `monitor.py` (`check_open_positions`; STOP wins tie in same candle; no timeout).
- `src/portfolio/`: `parser.py` (`parse_dossier` -> `(asset, days default 7 max 30)`, `parse_analyze` -> `asset`, plus trade/suportes parsers), `pricing.py` (`price_at` / `price_at_dt` via 1m closed candle), `store.py` (FIFO with `commit` flag + `recompute_fifo`), `listener.py` (`run_listener`; routes `/dossier`, `/analyze` with `validate_asset` + `command_allowed` + `ai_enabled` check), `monitor.py` (`check_portfolio_alerts` 5%/10% with hysteresis).
- `src/alerts/telegram.py`: alert template, `format_paper_open/close`, portfolio formatters, `format_council` (numbers from code facts only, never LLM), `format_dossier`, `format_diagnosis`, `get_updates`, send (honor `dry_run`).
- `src/costs.py`, `src/db.py`: fee/slippage (`backtest.fee_percent 0.1`, `slippage 0.05`) and DB helpers. `ensure_schema(conn, ai_enabled, embedding_dim)`: base tables always; `vector(768)` column + HNSW index only when `ai.enabled`; pgvector missing -> warn + SQL fallback, never crash.
- `doc/ARCHITECTURE.md`: module map, confusing points (injectable clock, non-persisted states).
- `README.md`: status table (`SIGNAL|WATCHING|NO_SETUP|NO_TRADE|REJECTED|INVALIDATED|TIMEOUT|COOLDOWN|SEND_FAILED|ERROR`) and manual verification.
- `Makefile`, `compose.yaml`, `Dockerfile`, `Dockerfile.db`, `.env.example`, `scripts/`, `data/` (local, do not version run outputs).

## Coding Rules (Crucial)
- Use Poetry exclusively. Run `poetry install`, `poetry run python main.py`, `poetry run python scripts/sanity_check.py`, `poetry run python scripts/dry_run_once.py`. Do not suggest `pip install`, `pip`, `conda`, or `npm`.
- Do not hardcode strategy params. Read everything from `config/config.yaml` via `load_config` (assets, EMAs, ATR period 14, touch_threshold 1.0%, atr_k 0.5, R/R 2.0, min 3% / preferred 5-10% / max_tp 50%, cooldown 12h, max_15m 16, exposure caps, supports block, `ai` block). `preferred_max_percent` is label only; real cap is `max_tp_percent`.
- Compute Market Filter once per cycle and reuse in memory (`cache_per_cycle: true`). Do not query per asset.
- Use only closed candles. `fetch_ohlcv` already excludes open candle; never use `raw[-1]` as signal; confirmation requires `candle_closed_only: true`.
- Follow pipeline order in `src/strategy/cycle.py:evaluate_asset` (see `README.md` pipeline section). Do not reorder Entry->Stop->Resistance->TP->return->R/R. Do not tighten Stop to meet R/R; discard trade instead.
- Persist state correctly: states `TOUCHED_EMA`/`CONFIRMED`/`COOLDOWN` are intra-cycle only, never write to DB. `REJECTED` does not exit WATCHING; exit only via TIMEOUT/invalidation/macro fail. `INVALIDATED` -> `NO_SETUP` next cycle; `ALERT_SENT` -> `NO_SETUP` after `cooldown_until_ts` expiry.
- Accept injectable clock: `evaluate_asset(..., now_ts)`, `exposure_ok/record_signal(..., now)`; production passes `None` (wall clock); tests inject epoch seconds (convert candle ms -> s).
- Respect idempotency: 1 paper OPEN per asset; `/venda` larger than open position is rejected with no write; `/edit`/`/delete`/`/old_*` use `recompute_fifo` with full rollback on `ValueError`; reject future dates.
- Validate Telegram input: only assets listed in `config.yaml` and only `TELEGRAM_CHAT_ID`; use existing parsers in `src/portfolio/parser.py` (`parse_dossier` caps days 1-30, `parse_analyze` strict `/analyze MOEDA`).
- AI layer constraints (fail-open, qualitative only): council runs only after `SIGNAL` in background with own connection; never blocks/delays the original alert; never vetoes or recalculates Entry/Stop/TP/R:R. LLM output must never contain numbers (`$`, `%`, long digits filtered in `llm.py`); Telegram numbers come from code facts only. Invalid JSON gets 1 repair retry, then silent skip (log + `council_reports.ok=0`, no follow-up). `submit` with `ai.enabled=false` is no-op. Enforce `command_allowed` (cooldown + daily cap) on `/dossier` and `/analyze`.
- RAG constraints: embedding failure must never break ingest (save row with `embedding NULL` for next-cycle backfill). Each row stores `embedding_model` + `embedding_dim`; changing the model requires deliberate re-embed (vectors are not comparable). Calibrate cutoffs with `scripts/rag_probe.py ASSET` before trusting `min_similarity` / `near_dup_similarity`.
- Match existing style: stdlib + listed deps only; no new exchange writes (read-only `ccxt`); no new DB tables without migration in `src/strategy/state.py` / `src/paper/store.py` / `src/portfolio/store.py` / `src/db.py` (`ensure_schema` + index); keep `[INFO]` log prefixes.
- Require `$DATABASE_URL`; if empty, fail fast with error. Do not add SQLite fallback.
- Never version run outputs under `data/`; never use `compose down -v` (pgdata volume holds production state).

## AI Response Guidelines
- Be concise and direct. State assumptions explicitly; surface tradeoffs; do not hide confusion.
- Do not explain basic concepts (Python, ccxt, Postgres, Telegram API) unless explicitly asked.
- Provide only modified code, with file path and minimal surrounding context. Do not paste full files.
- Prefer surgical edits: touch only what the request requires; match existing style; do not refactor adjacent code.
- Verify via execution when reasonable: `poetry run python scripts/sanity_check.py`, `poetry run python scripts/dry_run_once.py`, or `make sanity|dry-run`. For AI features use `poetry run python scripts/council_once.py --asset BTC --fake` (no cost), `poetry run python scripts/rag_probe.py BTC`, `poetry run python scripts/smoke_ai.py` (live API check).
- Use `make` shortcuts for Docker ops; use Poetry commands for Python runs. Never suggest `pip install`.
