# Arquitetura do Robit

Bot de alertas de swing trade cripto (spot, sem alavancagem, **não executa ordens**).
Especificação de negócio: `project.md`. Estado do projeto e achados: `README.md`.

## Mapa de módulos

```
main.py                           Loop contínuo: a cada novo candle 15m fechado, roda 1 ciclo
src/config/loader.py              Lê config/config.yaml + .env (TELEGRAM_BOT_TOKEN/CHAT_ID)
src/config/logging.py             Logs no formato "[INFO] ..." (§37 do project.md)

src/exchange/client.py            Wrapper ccxt/Binance (só leitura). fetch_ohlcv / fetch_warmup.
                                  Sempre descarta o último candle (possivelmente aberto).

src/market/providers/coingecko/   Preço atual (MarketSnapshot). Re-export via __init__.py.
src/market/providers/coinmktcap/  Preço atual + métricas globais. + fallback para coingecko.
src/market/providers/coinpaprika/ Preço + variações granulares (15m–24h) + beta + supply.
src/market/news/                  Notícias + classificação por IA.

src/strategy/indicators.py        EMA(20/50/100/200) + ATR(14) (§6.1).
src/strategy/filters.py           evaluate_market_filter (BTC, 1x por ciclo) + macro_pass (1D por ativo)
src/strategy/pullback.py          detect_pullback: EMA20>EMA50 + toque na EMA20/50 (% ou ATR) no 4H
src/strategy/state.py             Máquina de estados + Postgres (asset_state, daily_signals)
src/confirmation/confirm.py       reversal | ema_reclaim | any (OR dos dois). Só candles fechados.
src/strategy/risk.py              calc_stop_method (structure_atr | atr_only), find_resistance,
                                  calc_tp (TP = resistência + teto de sanidade 50%; faixa 5-10% é SÓ rótulo),
                                  risk_reward, position_size
src/exposure/manager.py           Caps de exposição (raramente ligam; ver Limitações).
                                  V4: contam posições paper OPEN (não mais estados WATCHING).
src/alerts/telegram.py            Template do alerta (§28) + envio (dry_run suprime).
                                  + format_paper_open/format_paper_close (V4, mensagens curtas)
src/strategy/cycle.py             evaluate_asset: pipeline completo por ativo (ordem §5 do project.md).
                                  run_cycle: após cada SIGNAL abre posição virtual (V4, _open_paper_position).
                                  Auto-rearme: INVALIDATED volta p/ NO_SETUP no próximo ciclo;
                                  ALERT_SENT volta p/ NO_SETUP após expirar o cooldown.
src/paper/store.py                Ledger virtual (tabela paper_positions): open/close/list/count.
                                  Entry guardado já com custo (apply_entry).
                                  Dedup: 1 OPEN por ativo (segunda abertura retorna None).
src/paper/monitor.py              check_open_positions: cada posição OPEN contra o último candle
                                  15m fechado (fetch_ohlcv já exclui candle aberto).
                                  Empate STOP+TP no mesmo candle → STOP (conservador).
                                  Sem timeout: OPEN até TP/STOP real (decisão V4).
```

## Reorganização V5 (mai/2024+)

Separação clara entre **dados** (market) e **lógica** (strategy):
- `src/market/`: fontes de preço (CoinGecko, CMC, Paprika) + notícias
- `src/strategy/`: análise técnica (indicadores, setup, risco, cycle)
- `src/config/`: load_config + setup_logging
- Demais: portfolio, paper trading, exchange, alertas

Ver `src/market/README.md` e `src/strategy/README.md` para convenções.

## V4 — Paper trading (ordem invertida vs project.md: V4 antes da V3)

```
run_cycle → SIGNAL → _open_paper_position (auto, fire-and-forget, saldo fixo risk.*)
main.py: após run_cycle → check_open_positions (mesmo candle 15m, mesmo loop)
scripts/paper_report.py → lista CLOSED (com PnL) + OPEN
```

- Config: `paper_trading.enabled` (default true p/ compat com configs antigas).
- Alertas: SIGNAL (existente) + PAPER ABERTA + PAPER FECHADA (com PnL).
- Dívida conhecida: sem V3, priorização de exposição em empate segue ordem da lista
  de ativos; limites (15/15) raramente ligam de qualquer forma.
- Critério p/ V3: ~30+ sinais reais fechados no ledger (abaixo disso, score/ranking
  são ruído). Com ~1 alerta/ativo/semestre, esperar ~1-2 anos de V4.

## Pipeline de um ciclo (`evaluate_asset`)

```
Market Filter (BTC, 1x/ciclo, reutilizado) → cooldown? → macro 1D → invalidação de WATCHING
→ pullback 4H → [NO_SETUP vira WATCHING] → confirmação 15m → entry/stop/resistência/TP
→ retorno mínimo → R/R ≥ mín → exposição → sizing → Telegram → ALERT_SENT + cooldown 12h
(auto-rearme: INVALIDATED→NO_SETUP no próximo ciclo; ALERT_SENT→NO_SETUP pós-cooldown)
```

Retorna 1 status por ativo: `SIGNAL | WATCHING | NO_SETUP | NO_TRADE | REJECTED |
INVALIDATED | TIMEOUT | COOLDOWN | SEND_FAILED | ERROR` (detalhes no README).

## Pontos que confundem (ler antes de mexer)

1. **Relógio injetável**: `evaluate_asset(..., now_ts)` e `exposure_ok/record_signal(..., now)`.
    Produção passa `None` (= wall clock); `now_ts` explícito serve p/ testes/diagnóstico.
    Cooldown/daily-buckets usam segundos epoch — converter ms→s se injetar timestamp de candle.
2. **Estados `TOUCHED_EMA`/`CONFIRMED`/`COOLDOWN` nunca são gravados** — `TOUCHED_EMA`/`CONFIRMED`
   são etapas intra-ciclo; cooldown é derivado de `cooldown_until_ts`, não de estado próprio.
3. **`REJECTED` não sai de WATCHING** — o estado persiste; a saída vem por TIMEOUT/invalidação/macro.
4. **TP sem teto de 10%**: `preferred_max_percent` é só classificação
   (`FAIXA PREFERENCIAL` / `ACIMA DA FAIXA PREFERENCIAL`); teto real é `max_tp_percent: 50`.
5. **Janela de confirmação (16) = 1 candle 4H**; o toque 4H só muda a cada 4h, então cada
   episódio tem ~1 janela efetiva. `pullback_low` é fixado na entrada em WATCHING (janela de 6×4H).

## Portfólio manual via Telegram (ortogonal ao motor de sinais)

```
main.py (thread daemon telegram-listener) → run_listener (getUpdates long-poll)
  → handle_text: /compra MOEDA,HH:MM,QTD | /venda ... | /troca DE,PARA,HH:MM,QTD
                 | /old_compra|/old_venda MOEDA,DD-MM-AAAA-HH:MM,QTD | /old_troca ...
                 | /extrato [MOEDA] | /historico [MOEDA]
                 | /edit ID,CAMPO,VALOR (hora: HH:MM ou DD-MM-AAAA-HH:MM)
                 | /delete ID | /help
src/portfolio/parser.py    parse_command + parse_troca + parse_old_command + parse_old_troca
                            + parse_edit + parse_delete + validate_asset (só assets do config)
src/portfolio/pricing.py   price_at (hoje) delega p/ price_at_dt (datetime explícito, p/ /old_* e /edit);
                            candle 1m fechado ≤ horário (since); fallback = preço atual
src/portfolio/store.py     portfolio_trades (ledger; remaining_qty por lote BUY) + weighted_avg
                            (BUY: só lotes abertos) + consume_fifo(commit flag)
                            + record_trade(commit flag) + realized_pnl
                            + get/update/delete_trade + recompute_fifo (rebuild por ativo);
                            portfolio_fifo_matches (1 linha por lote abatido: qty, preços, PnL)
src/portfolio/monitor.py   check_portfolio_alerts: a cada ciclo 15m, compara preço atual
                            com média ponderada (BUY: alta, só posição aberta; SELL: queda)
                            e com cada trade (lote BUY 100% vendido não alerta);
                            limiares 5%/10% com histerese (portfolio_alert_state; flags por trade)
Regra: /venda maior que a posição aberta é rejeitada (nada é gravado).
Regra: /edit e /delete recalculam o FIFO do ativo do zero (recompute_fifo); se alguma
       venda ficaria sem lote suficiente, a operação sofre rollback total (ValueError).
Regra: /troca = SELL(from, FIFO) + BUY(to, qty calculada pela cotação). /old_*
       inserem com commit=False + recompute_fifo (rollback total se inválido);
       datas futuras são rejeitadas.
/extrato = só lotes BUY em aberto + % vs cotação atual. /historico = vendas + PnL realizado.
/help = texto estático (format_help), sem acesso ao banco.
src/alerts/telegram.py     + get_updates + format_trade_confirmation/format_portfolio_alert/format_extrato
                            + format_historico/format_edit_confirmation/format_delete_confirmation
                            + format_troca_confirmation/format_help (when opcional p/ /old_*)
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

## Dados guardados (Postgres via `DATABASE_URL`, não versionar run outputs)

- Postgres — estado de produção (máquina de estados, paper trading, portfólio manual).

## Estado atual (não redescobrir)

Motor de sinais voltou a se rearmar sozinho: `INVALIDATED` retorna a `NO_SETUP` no
próximo ciclo e `ALERT_SENT` retorna a `NO_SETUP` após expirar o cooldown — antes
disso, ativos que já tinham alertado ficavam permanentemente travados (todos os 11
monitorados estavam presos desde 28/09, inclusive NEAR).
Estratégia segue **estruturalmente seletiva** (achado histórico das rodadas de
validação já removidas: ~70k toques → ~12-45 confirmações → ~4 sinais por 18m nos
majors, independente de R/R, janela, stop ou método de confirmação).
Defaults de produção: `reversal`, R/R 2.0, `structure_atr`.
