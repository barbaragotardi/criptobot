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

## Limitações conhecidas da V1

- **Prioridade de exposição**: os limites (`max_open_signals: 3`) são preenchidos na ordem da lista de ativos — BTC/ETH/XRP ocupam as vagas de `WATCHING` primeiro. Ranking de setups por qualidade é tema da V3.
- **Warm-up do 15m** (700 candles ≈ 7 dias) é curto para estabilizar a EMA200 nesse timeframe; o requisito de 700 candles do `project.md` mira o gráfico diário.
- Validação estatística da estratégia (backtest, walk-forward) é a **V2** — a V1 gera alertas segundo as regras, sem garantia de resultado.
