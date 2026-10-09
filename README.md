# Robit — Bot Assistente de Swing Trade Cripto (V1)

Bot que monitora criptomoedas e envia **alertas de possíveis oportunidades de swing trade em spot** (sem alavancagem) via Telegram.

Ele **não executa ordens**. O fluxo é: detectar setup → calcular entrada, stop, alvo e tamanho de posição → enviar alerta → **você decide** se opera manualmente na corretora.

## Como funciona (resumo do pipeline)

A cada ciclo, para cada ativo, o bot executa nesta ordem (`project.md` §5):

```
Filtro de mercado (BTC, 1× por ciclo)
  → Filtro macro 1D (preço > EMA200, EMA200 inclinada p/ cima, EMA20 > EMA50)
  → Setup de pullback 4H (toque na EMA20/EMA50)
  → Vigilância + confirmação 15m (candle de reversão)
  → Stop (fundo do pullback − ATR×K) → Resistência → Take Profit
  → Validações (retorno mínimo, R/R ≥ 2.0, exposição)
  → Posição simulada → Alerta no Telegram
```

Se qualquer etapa obrigatória falhar: **NO TRADE** (sem alerta).

## Status do ciclo (o que aparece no `RESULTS` e nos logs)

Cada ciclo retorna um status por ativo. É o diagnóstico mais direto do que o bot está "pensando":

| Status | Significado | O que fazer |
|---|---|---|
| `SIGNAL` | Setup completo: confirmação 15m + stop/TP/R-R/exposição aprovados. Alerta enviado (ou logado em dry-run). | Avaliar a operação manualmente. |
| `WATCHING` | Pullback 4H detectado, aguardando confirmação no 15m. O ativo fica em vigilância. | Nada — o bot está observando. Pode durar até 16 candles 15m (~4h). |
| `NO_SETUP` | Sem pullback válido no 4H (preço longe das EMAs ou EMA20 ≤ EMA50). Estado normal/ocioso. | Nada — não há nada no radar. |
| `NO_TRADE` | Bloqueado por filtro: mercado bearish (BTC abaixo da EMA200, ação `BLOCK`) ou macro 1D do ativo reprovado. | Nada — filtro de proteção atuando. |
| `REJECTED` | Setup existiu, mas foi descartado numa validação final: retorno abaixo do mínimo absoluto (3%), R/R < 2.0 ou limite de exposição. O log indica o motivo. | Nada — o setup não compensava o risco. Se vir muito `REJECTED` por R/R, reveja `min_risk_reward` no backtest (V2). |
| `INVALIDATED` | Havia vigilância aberta, mas o setup quebrou (fechamento 4H abaixo da EMA50 ou do fundo do pullback). | Nada — o bot abortou a vigilância. |
| `TIMEOUT` | Vigilância expirou: 16 candles 15m sem confirmação. Estado volta para `NO_SETUP`. | Nada. |
| `COOLDOWN` | Ativo dentro da janela de 12h após um alerta — novos sinais bloqueados para evitar spam do mesmo setup. | Aguardar o cooldown expirar. |
| `SEND_FAILED` | Sinal válido, mas o envio ao Telegram falhou (rede ou credencial). | Checar logs, `.env` e conectividade. |
| `ERROR` | Exceção inesperada no ciclo do ativo (ex: falha na API da exchange). Não afeta os outros ativos. | Checar o log de erro; o próximo ciclo tenta de novo. |

Exemplo de saída real de um ciclo (dry-run):

```
RESULTS: {'BTC': 'WATCHING', 'ETH': 'WATCHING', 'XRP': 'WATCHING',
          'SOL': 'NO_SETUP', 'LINK': 'NO_SETUP', ...}
```

## Estados persistidos (máquina de estados)

Além do status pontual do ciclo, cada ativo tem um **estado persistente** em SQLite que sobrevive a reinicializações (`project.md` §§25–27). Fluxo normal:

```
NO_SETUP → WATCHING → ALERT_SENT → (cooldown de 12h) → NO_SETUP
                                ↘ INVALIDATED (quebra ou timeout)
```

Estados possíveis na tabela `asset_state`:

| Estado | Significado |
|---|---|
| `NO_SETUP` | Ocioso, sem vigilância aberta. |
| `WATCHING` | Pullback detectado; contando candles 15m até confirmar ou expirar. Guarda `ema`, `pullback_low` e `candles_15m_waited`. |
| `ALERT_SENT` | Sinal gerado; guarda `entry`, `stop`, `tp`, `rr`, `last_alert_ts` e `cooldown_until_ts`. |
| `INVALIDATED` | Vigilância abortada por quebra estrutural. Volta a operar normalmente no próximo ciclo. |
| `TOUCHED_EMA` / `CONFIRMED` / `COOLDOWN` | Previstos no `project.md`, mas **não gravados pelo motor da V1**: `TOUCHED_EMA`/`CONFIRMED` são etapas intermediárias tratadas dentro do próprio ciclo, e o cooldown é derivado do campo `cooldown_until_ts` (verificado a cada ciclo) em vez de um estado próprio. |

## Setup

```bash
poetry install
cp .env.example .env   # preencher TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID
```

## Rodar

```bash
poetry run python main.py   # loop contínuo; dispara 1 ciclo a cada novo candle 15m fechado
```

Por padrão o bot roda em **dry-run** (`dry_run: true` em `config/config.yaml`): o alerta é impresso no log em vez de enviado. Para envio real, preencha o `.env` e ajuste `dry_run: false`.

## Configuração

Toda a estratégia vive em `config/config.yaml` (espelha a seção 33 do `project.md`): ativos, EMAs, ATR, filtros macro/mercado, limiar de toque, invalidação, stop, alvo (mínimo absoluto 3%, faixa preferencial 5–10%), R/R mínimo 2.0, risco simulado (saldo $1000, 1% por trade), exposição e cooldown. Nenhum parâmetro está hardcoded no código.

Três simplificações assumidas na V1 (detalhes no `project.md` eram abertos):

1. **Correlação**: todos os ativos exceto BTC formam um único grupo correlacionado (`max_correlated_exposure: 2`).
2. **Confirmação 15m**: 1 critério (engolfo de alta ou fechamento acima da máxima anterior); interface pronta para plugar outros.
3. **Resistência**: máxima dos últimos 50 candles 4H.

## Verificação manual (sem testes automatizados na V1)

```bash
# 1. Sanity numérico (reproduz os exemplos das seções 20 e 22 do project.md)
poetry run python scripts/sanity_check.py
# 2. Dry-run de 1 ciclo contra a Binance (somente leitura, não envia nada)
poetry run python scripts/dry_run_once.py
```

## Estado e logs

- SQLite em `data/robit.sqlite3`, tabela `asset_state`:
  ```bash
  sqlite3 data/robit.sqlite3 "SELECT asset, state, ema, entry, stop, tp, rr FROM asset_state ORDER BY asset;"
  ```
- Logs seguem o formato da seção 37 do `project.md`:
  ```
  [INFO] Market Filter - BTC: PASS
  [INFO] BTC - Macro filter: PASS (ok)
  [INFO] BTC - 4H EMA20 touch detected
  [INFO] BTC - 15m confirmation: WAIT (no_reversal)
  ```

## Backtest (V2a)

Replay do histórico através do mesmo pipeline de produção (`evaluate_asset` com relógio simulado), com saída simulada em candles 15m, taxa 0,1% por lado + slippage 0,05%.

```bash
poetry run python scripts/fetch_historical.py          # baixa cache parquet (1x)
poetry run python scripts/backtest.py --assets LTC --start 2024-01-01 --end 2024-12-31
poetry run python scripts/backtest.py --save /tmp/trades.json   # todos os ativos, histórico máximo
```

Saída: métricas da seção 31 do `project.md` (win rate, profit factor, drawdown, expectancy…) + breakdowns por ativo, ano e motivo de saída. Empate stop×TP no mesmo candle conta como STOP (conservador).

> **Achado do primeiro backtest (todos os 11 ativos, 2023-03→2026-09): 8 trades** (2 TP, 6 STOP, profit factor 1.03, retorno −0.5% — amostra pequena demais para concluir qualquer coisa). Funil medido: confirmação 15m passa em ~28% dos candles em geral, mas quase nunca dentro das janelas de vigilância pós-pullback — e quando passa, o R/R≥2 com stop estrutural de 6×4H reprova a maioria. Ou seja: com os parâmetros atuais, o filtro combinado é seletivo a ponto de gerar pouquíssima amostra. Isso é exatamente o que o V2b (comparação de parâmetros) vai explorar; o engine está verificado de ponta a ponta (slicing as-of bit-idêntico ao ao vivo, saída/custos/métricas checados numericamente, consistência entry<tp/stop validada nos 8 trades).

Limitações do V2a:

- Histórico 15m da Binance só vai até ~2023-03 (retenção da API) — o replay começa dali, não do listing.
- Exposure no backtest é por ativo (produção é portfolio-level) — raramente ligam; resultado tende a ser levemente otimista vs. produção.
- Breakdowns por confirmação/stop-method têm 1 único grupo (só existe 1 variante implementada de cada).

## V2b — Grid search, validação e teste (status: parado em achado)

Infra pronta: `scripts/param_sweep.py` (grid no Dev, paralelo), `validate_candidate.py` (1 config em Validação), `sensitivity.py` (OAT), `final_test.py` (Teste, só via `config/chosen_config.yaml` registrado). Splits fixos: Dev 2023-03→2024-09 / Validação →2025-09 / Teste →2026-09.

> **Resultado do grid (24 combinações, Dev, 4 ativos): todas com 2–4 trades — nenhuma atinge o mínimo de 10 para análise.** Ver `data/sweep_dev.csv`. Nem as combinações deliberadamente mais soltas (R/R 1.0, toque 2%) geram amostra. Sinais direcionais fracos (ex: `atr_only`+`reversal` = 0% win em 4/4; `ema_reclaim` com expectancy maior que `reversal`) existem, mas com n≤4 são ruído. **Decisão consciente: F7–F9 (validação/sensibilidade/teste final) não foram executados** — rodá-los sobre 2–4 trades seria teatro estatístico, não validação. Opções: (a) ampliar o grid ainda mais, (b) aceitar a baixa frequência como resultado, (c) revisar premissas da estratégia no `project.md`.

> **Busca dirigida aos gargalos (V2b revisado) — também esgotada.** Funil medido no Dev completo (4 ativos, 18m, ver `data/funnel_dev.txt`): 69.962 toques → 29 confirmações (0,04%) → 25 rejeitadas no R/R + 1 no retorno mínimo → **4 sinais**. Alargar a janela de confirmação de 4h até 24h (`max_15m_candles`: 16/32/48/96) **não adicionou nenhum trade** — os mesmos 4. Apertar o stop (`atr_multiplier` 0.5/0.75) zerou o win rate; afrouxar (1.5) reduziu para 1 trade (`data/levers_dev.txt`). Conclusão: a restrição vinculante é a coincidência "pullback 4H + reversão 15m", não a janela nem a distância do stop. **F7–F9 seguem não executados**; V2b encerra aqui com o achado documentado, sem forçar validação sobre amostra vazia.

> **Correção do teto de TP (pós-V2b).** Diagnóstico nas 24 rejeições por R/R: 21 bateram no teto artificial de 10% (`tp = min(resistance, entry×1.10)`), com resistência real mediana a 15,9% — o `project.md` §19 define 5–10% como *classificação*, não como teto. Removido o teto do cálculo (`calc_tp` usa só a resistência + teto de sanidade de 50%); a faixa virou só rótulo (`ACIMA DA FAIXA PREFERENCIAL` incluído) e flui automaticamente para o alerta do Telegram. Revalidação (`data/funnel_fixed.txt`): rejeições por R/R caíram 24→7, mas as confirmações continuam raras (12 em 18m) e os sinais continuam 4 — nem R/R 1.0/1.5 muda isso. **Teto real agora provado: ~12 confirmações/18m nos 4 ativos.** Próximo passo possível é revisar a lógica de entrada/confirmação (muda a identidade da estratégia) ou aceitar a raridade — decisão pendente.

> **Rodada final — confirmação combinada + touch/ATR (`data/funnel_any.txt`, `data/levers_round2.txt`). Tópico encerrado.** `confirmation.method: any` (`reversal` OR `ema_reclaim`) multiplicou confirmações por 3,75× (12→45), mas os sinais continuaram 4 — as extras morrem no R/R/retorno. Com `any` de base: R/R 1.0/1.5 → 4 trades; touch 2%/3% → 4; `atr_k` 1.0/1.5 → 4. **Todos os parâmetros testados em 3 rodadas convergem para os mesmos ~4 sinais/18m** — a seletividade é estrutural (coincidência macro + pullback + R/R), não paramétrica. Decisão final: **default de produção mantido** (`reversal`, R/R 2.0, TP sem teto — a correção do teto fica por ser bug genuíno); V1 gera alertas raros (~1 por ativo a cada 4–5 meses nos majors); amostra insuficiente para validação estatística com a retenção 15m da Binance (~2023-03 em diante). F7–F9 (validação/sensibilidade/teste) ficam construídos e documentados para quando houver mais histórico acumulado em produção real.

## Portfólio manual via Telegram

Registre suas compras/vendas reais pelo Telegram e receba alertas de +5%/+10%:

```text
/compra BTC,14:30,0.05   → registra 0.05 BTC ao preço do candle 1m das 14:30
/venda ETH,09:00,2       → idem para venda
/extrato                 → posições de compra em aberto + % vs cotação atual
/extrato BTC             → filtra por ativo
/historico               → vendas realizadas com lucro/perda ($ e %)
/historico BTC            → filtra por ativo
/edit 3,qtd,0.1          → altera a quantidade do registro #3
/edit 3,preco,65000      → altera o preço do registro #3
/edit 3,hora,14:30       → altera o horário do registro #3 (recalcula o preço)
/delete 3                → apaga o registro #3
```

- O preço é buscado na Binance no horário informado (fuso em `system.timezone`); se o candle ainda não fechou, usa o preço atual e avisa.
- Alerta de compra dispara em **alta** de 5%/10% sobre a referência; de venda, em **queda** de 5%/10%. Vale para o preço médio ponderado e para cada registro individual.
- **FIFO**: cada `/venda` abate os lotes de compra mais antigos primeiro (pelo horário informado) e a confirmação mostra o PnL realizado por lote. Venda maior que a posição aberta é rejeitada.
- **Edição/exclusão**: `/edit` e `/delete` recalculam o FIFO do ativo do zero. Se a operação deixaria alguma venda sem lote de compra suficiente para abater, ela é **rejeitada** e nada é alterado. Trocar o ativo ou o tipo (compra/venda) não é suportado — apague e registre de novo. Editar um registro antigo pode mudar retroativamente o PnL de vendas posteriores do mesmo ativo.
- Só aceita os ativos de `config.yaml` e mensagens do `TELEGRAM_CHAT_ID` configurado.

## Limitações conhecidas da V1

- **Prioridade de exposição**: os limites (`max_open_signals: 3`) são preenchidos na ordem da lista de ativos — BTC/ETH/XRP ocupam as vagas de `WATCHING` primeiro. Ranking de setups por qualidade é tema da V3.
- **Warm-up do 15m** (700 candles ≈ 7 dias) é curto para estabilizar a EMA200 nesse timeframe; o requisito de 700 candles do `project.md` mira o gráfico diário.
- Validação estatística da estratégia (backtest, walk-forward) é a **V2** — a V1 gera alertas segundo as regras, sem garantia de resultado.
