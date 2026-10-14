# Paper Trading

Simulação automática de posições abertas.

## Módulos

- `store.py` — Ledger `paper_positions` (Postgres): OPEN/CLOSED com entry, exit, PnL
- `monitor.py` — `check_open_positions(conn, exchange, cfg)`: fecha posições se atingem STOP ou TP

## Fluxo

1. `run_cycle()` detecta SIGNAL (confirmação + validações OK)
2. Abre posição virtual automaticamente (fire-and-forget, sem confirmação manual)
3. `check_open_positions()` verifica a cada ciclo 15m se atingiu STOP/TP
4. Fecha com PnL calculado + mensagem de fechamento no Telegram
5. `scripts/paper_report.py` — lista CLOSED (com PnL) + OPEN

## Configuração

Via `config/config.yaml`:
```yaml
paper_trading:
  enabled: true   # default true
```

## Notas

- 1 OPEN por ativo (segunda abertura ignora)
- Empate STOP+TP no mesmo candle → STOP (conservador)
- Sem timeout: OPEN até TP/STOP real
- Alertas: PAPER ABERTA + PAPER FECHADA (com PnL)
