# Portfolio

Gerenciamento manual de trades via Telegram (ortogonal ao motor de sinais automáticos).

## Módulos

- `listener.py` — `run_listener(cfg, now)`: long-poll `getUpdates`, despacha comandos de trade
- `parser.py` — Parse de comandos (`/compra`, `/venda`, `/troca`, `/old_*`, `/edit`, `/delete`, `/help`)
- `pricing.py` — `price_at(ativo)` / `price_at_dt(ativo, dt)`: preço atual ou histórico
- `store.py` — FIFO ledger (BUY/SELL + PnL), `weighted_avg`, `realized_pnl`
- `monitor.py` — `check_portfolio_alerts(conn, exchange, cfg)`: a cada ciclo, alertas de atingimento de metas BUY/SELL

## Comandos

- `/compra MOEDA,HH:MM,QTD` — registro de compra hoje
- `/venda MOEDA,HH:MM,QTD` — registro de venda hoje
- `/troca DE,PARA,HH:MM,QTD` — venda DE + compra PARA (preço/hora iguais)
- `/old_compra|/old_venda|/old_troca MOEDA,DD-MM-AAAA-HH:MM,QTD` — histórico
- `/edit ID,CAMPO,VALOR` — ajustar hora/qtd de trade existente
- `/delete ID` — remover trade
- `/extrato [MOEDA]` — posição atual (BUY+SELL com PnL)
- `/historico [MOEDA]` — histórico de trades fechados
- `/help` — lista de comandos

## Notas

- FIFO: BUY abre lote, SELL consome ordem FIFO de lotes abertos
- Preço: `/old_*` busca 1º candle 1m fechado ≤ hora (fallback = preço atual)
- Validação: só assets em `cfg["assets"]`
