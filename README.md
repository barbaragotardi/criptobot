# Robit — Bot Assistente de Swing Trade Cripto

Bot que monitora criptomoedas e envia **alertas de possíveis oportunidades de swing trade em spot** (sem alavancagem) via Telegram. **Não executa ordens**. O fluxo é: detectar setup → calcular entrada, stop, alvo e tamanho de posição → enviar alerta → **você decide** se opera manualmente na corretora.

## Arquitetura

```
src/
├── config/            Config (load_config, setup_logging)
├── market/            Fontes de dados: preço (CoinGecko/CMC/Paprika) + notícias
├── strategy/          Motor de análise: indicadores, setup, risco, ciclo
├── exchange/          Wrapper ccxt/Binance (leitura apenas)
├── portfolio/         Gerenciador manual de trades via Telegram
├── paper/             Paper trading: simulação de posições abertas
├── alerts/            Formatação + envio de alertas (Telegram)
└── ...                
```

Veja `doc/ARCHITECTURE.md` para mapa completo.

## Pipeline do ciclo

A cada ciclo, para cada ativo, o bot executa nesta ordem (`project.md` §5):

```
Filtro de mercado (BTC, 1× por ciclo)
  → Filtro macro 1D (preço > EMA200, EMA200 inclinada p/ cima, EMA20 > EMA50)
  → Setup de pullback 4H (toque na EMA20/EMA50)
  → Vigilância + confirmação 15m (candle de reversão)
  → Stop (fundo do pullback − ATR×K) → Resistência → Take Profit
  → Validações (retorno mínimo, R/R ≥ 2.0, exposição)
  → Paper trading (simulação) → Alerta no Telegram
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
| `REJECTED` | Setup existiu, mas foi descartado numa validação final: retorno abaixo do mínimo absoluto (3%), R/R < 2.0 ou limite de exposição. O log indica o motivo. | Nada — o setup não compensava o risco. Se vir muito `REJECTED` por R/R, reveja `min_risk_reward` no `config/config.yaml`. |
| `INVALIDATED` | Havia vigilância aberta, mas o setup quebrou (fechamento 4H abaixo da EMA50 ou do fundo do pullback). O ativo volta para `NO_SETUP` no próximo ciclo e pode gerar novo setup. | Nada — o bot abortou a vigilância e se rearma sozinho. |
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

## Portfólio manual via Telegram

Registre suas compras/vendas reais pelo Telegram e receba alertas de +5%/+10%:

```text
/compra BTC,14:30,0.05   → registra 0.05 BTC ao preço do candle 1m das 14:30
/venda ETH,09:00,2       → idem para venda
/troca NEAR,ETH,13:50,70.5 → troca 70.5 NEAR por ETH (qtd de ETH calculada pela cotação)
/old_compra BTC,30-12-2025-14:54,0.1 → compra antiga (com data completa)
/old_venda BTC,15-01-2026-10:00,0.05 → venda antiga
/old_troca NEAR,ETH,15-01-2026-13:50,70.5 → troca antiga
/extrato                 → posições de compra em aberto + % vs cotação atual
/extrato BTC             → filtra por ativo
/historico               → vendas realizadas com lucro/perda ($ e %)
/historico BTC            → filtra por ativo
/edit 3,qtd,0.1          → altera a quantidade do registro #3
/edit 3,preco,65000      → altera o preço do registro #3
/edit 3,hora,14:30       → altera o horário do registro #3 (recalcula o preço)
/edit 3,hora,30-12-2025-14:54 → idem com data completa (para registros antigos)
/delete 3                → apaga o registro #3
/help                    → lista todos os comandos com exemplos
```

- O preço é buscado na Binance no horário informado (fuso em `system.timezone`); se o candle ainda não fechou, usa o preço atual e avisa.
- Alerta de compra dispara em **alta** de 5%/10% sobre a referência; de venda, em **queda** de 5%/10%. Vale para o preço médio ponderado e para cada registro individual.
- **FIFO**: cada `/venda` abate os lotes de compra mais antigos primeiro (pelo horário informado) e a confirmação mostra o PnL realizado por lote. Venda maior que a posição aberta é rejeitada.
- **Edição/exclusão**: `/edit` e `/delete` recalculam o FIFO do ativo do zero. Se a operação deixaria alguma venda sem lote de compra suficiente para abater, ela é **rejeitada** e nada é alterado. Trocar o ativo ou o tipo (compra/venda) não é suportado — apague e registre de novo. Editar um registro antigo pode mudar retroativamente o PnL de vendas posteriores do mesmo ativo.
- **Troca**: `/troca` registra uma venda do ativo de origem (abatendo FIFO e realizando PnL) + uma compra do ativo de destino. A quantidade recebida é calculada pela cotação dos dois ativos no horário informado (pode divergir um pouco da taxa real da corretora/DEX, que não conta slippage nem taxas).
- **Registros antigos**: `/old_compra`, `/old_venda` e `/old_troca` aceitam data completa (`DD-MM-AAAA-HH:MM`), buscam o candle histórico na Binance e recalculam o FIFO do ativo — o PnL de vendas já confirmadas pode mudar retroativamente se a ordem cronológica real for diferente da ordem de registro. Datas futuras são rejeitadas.
- Só aceita os ativos de `config.yaml` e mensagens do `TELEGRAM_CHAT_ID` configurado.
