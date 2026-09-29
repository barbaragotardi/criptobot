# Arquitetura do Robit

Bot de alertas de swing trade cripto (spot, sem alavancagem, **não executa ordens**).
Especificação de negócio: `project.md`. Estado do projeto e achados: `README.md`.

## Mapa de módulos

```
main.py                  Loop contínuo: a cada novo candle 15m fechado, roda 1 ciclo
src/config.py            Lê config/config.yaml + .env (TELEGRAM_BOT_TOKEN/CHAT_ID)
src/logging_config.py    Logs no formato "[INFO] ..." (§37 do project.md)

src/exchange/client.py   Wrapper ccxt/Binance (só leitura). fetch_ohlcv / fetch_warmup.
                         Sempre descarta o último candle (possivelmente aberto).
src/indicators/engine.py EMA(20/50/100/200) + ATR(14). MESMAS funções no live e no backtest (§6.1).
src/filters/filters.py   evaluate_market_filter (BTC, 1x por ciclo) + macro_pass (1D por ativo)
src/setup/pullback.py    detect_pullback: EMA20>EMA50 + toque na EMA20/50 (% ou ATR) no 4H
src/setup/state.py       Máquina de estados + SQLite (asset_state, daily_signals)
src/confirmation/confirm.py  reversal | ema_reclaim | any (OR dos dois). Só candles fechados.
src/risk/engine.py       calc_stop_method (structure_atr | atr_only), find_resistance,
                         calc_tp (TP = resistência + teto de sanidade 50%; faixa 5-10% é SÓ rótulo),
                         risk_reward, position_size
src/exposure/manager.py  Caps de exposição (raramente ligam; ver Limitações).
                          V4: contam posições paper OPEN (não mais estados WATCHING).
src/alerts/telegram.py   Template do alerta (§28) + envio (dry_run suprime).
                          + format_paper_open/format_paper_close (V4, mensagens curtas)
src/engine/cycle.py      evaluate_asset: pipeline completo por ativo (ordem §5 do project.md).
                          run_cycle: após cada SIGNAL abre posição virtual (V4, _open_paper_position).
                          evaluate_asset NÃO abre posição — backtest chama evaluate_asset
                          direto, então o replay nunca toca no ledger paper.
src/paper/store.py       Ledger virtual (tabela paper_positions): open/close/list/count.
                          Colunas espelham o dict de trade do backtest (open_ts em ms,
                          exit_reason, pnl_pct, rr) p/ reuso direto de metrics.summarize.
                          Entry guardado já com custo (apply_entry), igual ao backtest.
                          Dedup: 1 OPEN por ativo (segunda abertura retorna None).
src/paper/monitor.py     check_open_positions: cada posição OPEN contra o último candle
                          15m fechado (fetch_ohlcv já exclui candle aberto).
                          Regra idêntica ao exit_simulator (empate STOP+TP → STOP).
                          Sem timeout: OPEN até TP/STOP real (decisão V4).
```

## V4 — Paper trading (ordem invertida vs project.md: V4 antes da V3)

```
run_cycle → SIGNAL → _open_paper_position (auto, fire-and-forget, saldo fixo risk.*)
main.py: após run_cycle → check_open_positions (mesmo candle 15m, mesmo loop)
scripts/paper_report.py → summarize + breakdown por ativo sobre CLOSED
```

- Config: `paper_trading.enabled` (default true p/ compat com configs antigas).
- Alertas: SIGNAL (existente) + PAPER ABERTA + PAPER FECHADA (com PnL).
- Dívida conhecida: sem V3, priorização de exposição em empate segue ordem da lista
  de ativos; limites (15/15) raramente ligam de qualquer forma.
- Impacto no backtest: `exposure_ok` agora conta paper OPEN (sempre 0 no replay) em
  vez de WATCHING — no replay a exposição efetivamente nunca bloqueia, o que é
  consistente com a limitação já documentada (caps raramente ligavam).
- Critério p/ V3: ~30+ sinais reais fechados no ledger (abaixo disso, score/ranking
  são ruído). Com ~1 alerta/ativo/semestre, esperar ~1-2 anos de V4.

## Pipeline de um ciclo (`evaluate_asset`)

```
Market Filter (BTC, 1x/ciclo, reutilizado) → cooldown? → macro 1D → invalidação de WATCHING
→ pullback 4H → [NO_SETUP vira WATCHING] → confirmação 15m → entry/stop/resistência/TP
→ retorno mínimo → R/R ≥ mín → exposição → sizing → Telegram → ALERT_SENT + cooldown 12h
```

Retorna 1 status por ativo: `SIGNAL | WATCHING | NO_SETUP | NO_TRADE | REJECTED |
INVALIDATED | TIMEOUT | COOLDOWN | SEND_FAILED | ERROR` (detalhes no README).

## Pontos que confundem (ler antes de mexer)

1. **Relógio injetável**: `evaluate_asset(..., now_ts)` e `exposure_ok/record_signal(..., now)`.
   Produção passa `None` (= wall clock); backtest passa o timestamp do candle.
   Cooldown/daily-buckets usam segundos epoch — converter ms→s no replay.
2. **Estados `TOUCHED_EMA`/`CONFIRMED`/`COOLDOWN` nunca são gravados** — `TOUCHED_EMA`/`CONFIRMED`
   são etapas intra-ciclo; cooldown é derivado de `cooldown_until_ts`, não de estado próprio.
3. **`REJECTED` não sai de WATCHING** — o estado persiste; a saída vem por TIMEOUT/invalidação/macro.
4. **TP sem teto de 10%**: `preferred_max_percent` é só classificação
   (`FAIXA PREFERENCIAL` / `ACIMA DA FAIXA PREFERENCIAL`); teto real é `max_tp_percent: 50`.
5. **Janela de confirmação (16) = 1 candle 4H**; o toque 4H só muda a cada 4h, então cada
   episódio tem ~1 janela efetiva. `pullback_low` é fixado na entrada em WATCHING (janela de 6×4H).
6. **Backtest é per-asset com DB `:memory:` isolado** — caps de exposição (portfolio-level em
   produção) raramente ligam no replay. Resultado tende a ser levemente otimista.

## Portfólio manual via Telegram (ortogonal ao motor de sinais)

```
main.py (thread daemon telegram-listener) → run_listener (getUpdates long-poll)
  → handle_text: /compra MOEDA,HH:MM,QTD | /venda ... | /extrato [MOEDA]
src/portfolio/parser.py    parse_command + validate_asset (só assets do config)
src/portfolio/pricing.py   price_at: candle 1m fechado ≤ horário (since); fallback = preço atual
src/portfolio/store.py     portfolio_trades (ledger; remaining_qty por lote BUY) + weighted_avg
                            (BUY: só lotes abertos) + consume_fifo + realized_pnl;
                            portfolio_fifo_matches (1 linha por lote abatido: qty, preços, PnL)
src/portfolio/monitor.py   check_portfolio_alerts: a cada ciclo 15m, compara preço atual
                            com média ponderada (BUY: alta, só posição aberta; SELL: queda)
                            e com cada trade (lote BUY 100% vendido não alerta);
                            limiares 5%/10% com histerese (portfolio_alert_state; flags por trade)
Regra: /venda maior que a posição aberta é rejeitada (nada é gravado).
src/portfolio/monitor.py   check_portfolio_alerts: a cada ciclo 15m, compara preço atual
                            com média ponderada (BUY: alta; SELL: queda) e com cada trade;
                            limiares 5%/10% com histerese (portfolio_alert_state; flags por trade)
src/alerts/telegram.py     + get_updates + format_trade_confirmation/format_portfolio_alert/format_extrato
Tabelas: portfolio_trades, portfolio_alert_state, telegram_offset (offset do getUpdates)
Segurança: só processa mensagens do chat_id configurado.
```

## Backtest (`src/backtest/`)

```
data_cache.py   Baixa histórico completo → data/historical/{ATIVO}_{1D,4H,15m}.parquet
clock.py        frames_at (exato, 1 passo) + Replayer (cache por TF; bit-idêntico ao ao vivo)
exit_simulator.py  Caminha 15m após a entrada até stop ou TP (empate no mesmo candle → STOP)
costs.py        Fee 0,1% + slippage 0,05% por lado, contra o trader
runner.py       Replay 15m→15m chamando evaluate_asset; dry_run forçado; grava trades
metrics.py      12 métricas (§31) + breakdown por ativo/ano/motivo
parallel.py     Mesma coisa em ProcessPoolExecutor (workers carregam próprio parquet)
splits.py       Dev 2023-03→2024-09 / Validação →2025-09 / Teste →2026-09 (fixos, anti-peeking)
param_grid.py   Overrides dotted ("risk.min_risk_reward") + produto cartesiano
```

Scripts: `fetch_historical.py`, `backtest.py` (`--assets/--start/--end/--save`),
`funnel.py` (conta statuses + motivos de rejeição no log), `lever.py`
(varia 1 parâmetro no Dev), `param_sweep.py` (grid no Dev), `validate_candidate.py`,
`sensitivity.py`, `final_test.py` (só via `config/chosen_config.yaml` registrado).

## Dados e resultados guardados (`data/`, não versionar run outputs)

- `historical/` — cache parquet (15m só existe desde ~2023-03: retenção da Binance).
- `robit.sqlite3` — estado de produção. Backtest nunca toca aqui.
- `funnel_*.txt`, `levers_*.txt`, `sweep_dev.csv` — evidências das rodadas V2b (amostra ~4 sinais).

## Estado atual (não redescobrir)

Estratégia validada como **estruturalmente seletiva**: ~70k toques → ~12-45 confirmações →
~4 sinais por 18m (4 majors). Todas as alavancas testadas (janela até 24h, R/R 1.0–2.0,
stop atr_only, confirmação any, touch até 3%, atr_k até 1.5) convergem pros mesmos ~4.
Defaults de produção congelados: `reversal`, R/R 2.0, `structure_atr`. Próximo passo
depende de decisão de estratégia (ver README), não de mais tuning.
