# Strategy

Lógica de trade: filtro → setup → risco → ciclo.

## Estrutura

- `cycle.py` — `run_cycle(cfg, conn, exchange)`: orquestra um ciclo de análise.
- `filters.py` — `evaluate_market_filter()`, `macro_pass()`: filtros de mercado e macro 1D.
- `pullback.py` — `detect_pullback()`: setup de pullback no 4H.
- `risk.py` — `calc_stop*()`, `find_resistance()`, `calc_tp()`, `position_size()`, `risk_reward()`.
- `indicators.py` — `add_indicators()`: EMAs + ATR sobre os candles.
- `state.py` — `connect_cfg()`, `get_state()`/`set_state()`, `in_cooldown()`: persistência Postgres.

## Convenções

- `cycle.py` é o único ponto de entrada; demais módulos são funções puras (exceto `state.py`).
- Entrada: `main.py` e `scripts/dry_run_once.py`.
