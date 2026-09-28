# Projeto: Bot Assistente de Swing Trade Cripto

## 1. Objetivo

Criar um robô assistente pessoal que monitora continuamente o mercado de criptomoedas e envia alertas de possíveis oportunidades de **Swing Trade em Spot**, sem alavancagem.

O bot **não executa operações automaticamente**. Sua função é:

1. Monitorar os ativos definidos.
2. Identificar configurações que atendam aos critérios da estratégia.
3. Calcular parâmetros de entrada, risco, retorno e tamanho de posição.
4. Enviar um alerta pelo Telegram.
5. Permitir que o usuário decida manualmente se realizará a operação.

A estratégia busca operações com potencial preferencialmente entre **5% e 10% de valorização**, com um mínimo absoluto configurável. Essa faixa não representa garantia de resultado.

---

# 2. Ativos Monitorados

O bot inicialmente monitora:

```text
BTC
ETH
XRP
SOL
LINK
XLM
BCH
NEAR
UNI
LTC
AVAX
```

Os ativos devem possuir liquidez suficiente na corretora utilizada.

A arquitetura deve permitir adicionar ou remover ativos posteriormente sem alteração na lógica principal.

---

# 3. Timeframes

A estratégia utiliza três níveis de timeframe:

```text
1D  → Filtro de tendência macro
4H  → Identificação do setup e pullback
15m → Confirmação rápida da entrada
```

O gráfico de 15 minutos **não define a tendência principal**. Sua função é confirmar a reversão após o setup ter sido identificado no gráfico de 4H.

---

# 4. Indicadores

O setup utiliza:

```text
EMA 20
EMA 50
EMA 100
EMA 200
ATR
```

As EMAs devem ser calculadas sobre o preço de fechamento dos candles.

O ATR será utilizado principalmente para estimar a volatilidade e auxiliar na definição do Stop Loss.

---

# 5. Estrutura da Estratégia

O processo de análise deve seguir esta ordem:

```text
Market Filter
   ↓
Filtro macro 1D
   ↓
Filtro do ativo
   ↓
Setup de pullback 4H
   ↓
Detecção da zona de entrada
   ↓
Vigilância 15m
   ↓
Confirmação da reversão
   ↓
Cálculo do Stop
   ↓
Análise de resistência
   ↓
Cálculo do Take Profit
   ↓
Validação do retorno mínimo
   ↓
Validação do Risk/Reward
   ↓
Cálculo do tamanho da posição
   ↓
Geração do alerta
```

Um ativo somente poderá gerar sinal se passar por todas as etapas obrigatórias.

---

# 6. Dados Históricos e Warm-up das EMAs

O Data Processor deve carregar histórico suficiente antes de iniciar os cálculos dos indicadores.

Para o gráfico diário:

```yaml
data:
  daily_initial_candles: 700
```

O objetivo é reduzir o efeito do valor inicial da EMA200.

O mesmo processo deve ser aplicado aos demais timeframes de acordo com o indicador de maior período utilizado.

## 6.1 Consistência

O cálculo utilizado no:

```text
Backtest
Paper Trading
Produção
```

deve ser exatamente o mesmo.

A quantidade de candles de warm-up e a metodologia de inicialização das EMAs devem ser mantidas consistentes entre os ambientes.

> O uso de 700 candles reduz o efeito de inicialização, mas não garante que o valor será matematicamente idêntico ao TradingView, pois isso depende também do histórico utilizado e da metodologia de inicialização.

---

# 7. Filtro Macro — Gráfico Diário (1D)

O objetivo é evitar operações contra uma tendência macro de baixa.

## 7.1 Condição mínima

O preço de fechamento do último candle diário fechado deve estar acima da EMA200:

```text
Close_1D > EMA200_1D
```

## 7.2 Inclinação da EMA200

A EMA200 deve apresentar inclinação positiva:

```text
EMA200 atual > EMA200 de N candles atrás
```

Configuração:

```yaml
macro:
  ema200_slope_required: true
  slope_periods: 5
```

## 7.3 Estrutura de tendência

Como filtro adicional:

```text
EMA20_1D > EMA50_1D
```

Esse filtro deve permanecer configurável.

---

# 8. Filtro de Mercado

Como diferentes criptomoedas possuem alta correlação, o bot deve considerar a condição geral do mercado.

O BTC será utilizado inicialmente como referência.

Condição:

```text
BTC Close_1D > BTC EMA200_1D
```

O filtro deve ser processado **uma única vez no início de cada ciclo de análise**.

Exemplo:

```python
market_bullish = evaluate_market_filter()
```

Os ativos analisados posteriormente devem reutilizar esse resultado em memória.

Não devem ser feitas consultas repetidas à API para recalcular o mesmo filtro durante o mesmo ciclo.

Configuração:

```yaml
market_filter:
  enabled: true
  reference_asset: BTC
  bearish_action: BLOCK
```

Valores possíveis:

```text
BLOCK
REDUCE
ALLOW
```

---

# 9. Filtro do Ativo

Depois do Market Filter, cada ativo deve passar pelo próprio filtro macro.

Para ativos diferentes do BTC:

```text
Close_1D > EMA200_1D
EMA200_1D com inclinação positiva
EMA20_1D > EMA50_1D
```

Para o BTC, o resultado do filtro de mercado já calculado deve ser reutilizado quando possível, evitando processamento e requisições duplicadas.

---

# 10. Setup de Pullback — Gráfico 4H

Após passar pelos filtros anteriores, o bot procura um pullback no gráfico de 4H.

Condição inicial:

```text
EMA20_4H > EMA50_4H
```

O preço deve então corrigir em direção às zonas de suporte dinâmico.

---

# 11. Zonas de Suporte Dinâmico

As principais zonas utilizadas serão:

```text
EMA20_4H
EMA50_4H
```

A EMA100 e EMA200 podem ser utilizadas como informações adicionais, mas não são gatilhos primários.

---

# 12. Definição Objetiva de "Toque"

O sistema não deve depender de interpretação visual.

```text
distance = abs(price - EMA) / price
```

Um toque será considerado válido quando:

```text
distance <= TOUCH_THRESHOLD
```

Configuração inicial:

```yaml
entry:
  touch_threshold_percent: 1.0
```

Esse valor deve ser testado durante o backtest.

---

# 13. Normalização por Volatilidade

Como diferentes criptomoedas possuem volatilidades diferentes, o sistema também deve permitir o uso do ATR.

Exemplo:

```text
distance_to_ema <= ATR * K
```

O sistema deve permitir comparar no backtest:

```text
Percentual fixo
vs.
Distância baseada em ATR
```

---

# 14. Ativação da Vigilância 15m

Quando um pullback válido for detectado no gráfico de 4H, o ativo entra no estado:

```text
WATCHING
```

A partir desse momento, o bot passa a observar o gráfico de 15 minutos.

Fluxo:

```text
4H detecta pullback
        ↓
Zona EMA20/EMA50 atingida
        ↓
Ativa vigilância 15m
        ↓
Aguarda confirmação
```

---

# 15. Confirmação da Entrada — 15m

O sinal de entrada será confirmado no gráfico de 15 minutos.

O bot deve trabalhar somente com candles de 15m fechados para a confirmação.

Possíveis critérios:

* candle de reversão;
* fechamento acima da máxima do candle anterior;
* fechamento recuperando a EMA testada;
* formação de fundo local;
* rompimento de uma pequena estrutura de baixa.

O critério utilizado deve ser configurável.

```yaml
confirmation:
  timeframe: 15m
  candle_closed_only: true
  require_reversal: true
```

---

# 16. Entrada

Após a confirmação no 15m, o sistema registra o preço de entrada.

Por padrão:

```text
entry_price = close do candle de confirmação
```

Alternativamente, poderá ser testada entrada no rompimento da máxima do candle de confirmação.

---

# 17. Stop Loss

O Stop Loss **não deve ser derivado do Take Profit**.

Primeiro deve ser determinado o ponto de invalidação da estrutura.

Possíveis referências:

* fundo formado durante o pullback;
* suporte relevante;
* distância baseada em ATR.

Exemplo:

```text
stop = pullback_low - (ATR * K)
```

Configuração inicial:

```yaml
risk:
  stop_method: structure_atr
  atr_multiplier: 1.0
```

O Stop deve ficar suficientemente distante para evitar saídas causadas apenas pelo ruído normal do mercado.

---

# 18. Resistência e Espaço Disponível

Antes de definir o Take Profit, o bot deve identificar possíveis regiões de resistência:

* máxima recente;
* topo local;
* máxima relevante anterior;
* região de consolidação;
* resistência estrutural identificada pelo histórico.

Cálculo:

```text
distance_to_resistance =
(resistance - entry_price) / entry_price
```

---

# 19. Take Profit

O Take Profit não deve ser definido simplesmente como uma porcentagem fixa.

Processo:

```text
1. Definir Entry
2. Definir Stop
3. Identificar resistência
4. Calcular espaço disponível
5. Definir TP possível
6. Validar retorno mínimo
7. Calcular Risk/Reward
8. Validar R/R mínimo
```

A faixa:

```text
5% a 10%
```

será considerada a **faixa preferencial de Swing Trade**.

Entretanto, o sistema deverá possuir um limite absoluto mínimo:

```yaml
target:
  absolute_min_percent: 3.0
  preferred_min_percent: 5.0
  preferred_max_percent: 10.0
```

## 19.1 Regra do alvo

O trade será descartado se:

```text
potential_return < absolute_min_percent
```

Se:

```text
absolute_min_percent <= potential_return < preferred_min_percent
```

o trade poderá ser aceito, desde que o R/R e os demais critérios sejam atendidos.

Porém, o alerta deverá indicar:

```text
Target: abaixo da faixa preferencial
```

Isso permite diferenciar operações de retorno menor de setups dentro da faixa principal da estratégia.

Se:

```text
potential_return >= preferred_min_percent
```

o setup estará dentro da faixa preferencial.

---

# 20. Relação Risco/Retorno

Depois que Stop e Take Profit forem definidos:

```text
risk = entry - stop

reward = target - entry

risk_reward = reward / risk
```

Configuração inicial:

```yaml
risk:
  min_risk_reward: 2.0
```

O bot **não deve apertar artificialmente o Stop para atingir o R/R mínimo**.

Se o Stop estrutural/ATR resultar em um R/R abaixo do mínimo:

```text
TRADE DESCARTADO
```

Exemplo:

```text
Entry: 100
Stop: 94
Risk: 6%

TP: 106
Reward: 6%

R/R: 1.0
```

Resultado:

```text
TRADE DESCARTADO
```

---

# 21. Validação Final do Trade

O sinal somente será aprovado se:

```text
Market Filter = aprovado
AND
Filtro 1D = aprovado
AND
Pullback 4H = válido
AND
Confirmação 15m = válida
AND
Stop = válido
AND
Retorno >= absolute_min_percent
AND
Espaço até resistência = suficiente
AND
Risk/Reward >= mínimo
```

Caso qualquer condição obrigatória falhe:

```text
NO TRADE
```

---

# 22. Gerenciamento de Risco e Tamanho da Posição

O bot deve calcular uma sugestão de tamanho de posição sem depender da integração com o saldo real da corretora.

Será utilizado um saldo configurável para simulação:

```yaml
risk:
  simulated_account_balance: 1000
  max_risk_per_trade_percent: 1.0
```

Exemplo:

```text
Saldo simulado: $1.000
Risco por operação: 1%

Capital máximo em risco:
$1.000 × 1% = $10
```

O tamanho da posição será calculado com base na distância entre entrada e Stop:

```text
capital_risk =
simulated_account_balance * risk_per_trade

position_size =
capital_risk / stop_distance
```

Exemplo:

```text
Entry: $100
Stop: $95
Stop distance: 5%

Capital em risco: $10

Position size:
$10 / 5% = $200
```

O alerta do Telegram poderá apresentar:

```text
Saldo de referência: $1.000
Risco máximo: 1%
Risco financeiro: $10
Posição sugerida: $200
```

Esse valor é **apenas uma simulação** e não representa o saldo real da conta.

Quando houver integração futura com a corretora, o saldo real poderá substituir o valor simulado.

---

# 23. Exposição e Correlação

Como diferentes criptomoedas podem se movimentar de maneira altamente correlacionada, o sistema deve controlar a exposição simultânea.

Configuração:

```yaml
exposure:
  max_open_signals: 3
  max_signals_per_day: 5
  max_correlated_exposure: 2
```

Esses valores devem ser ajustados através de backtesting.

---

# 24. Deduplicação de Alertas

O bot não deve enviar vários alertas para o mesmo evento.

Exemplo:

```text
BTC → EMA50 → sinal confirmado
```

Após gerar o sinal, novos alertas para o mesmo setup devem ser bloqueados durante um período configurável.

```yaml
system:
  cooldown_hours: 12
```

Um novo sinal somente poderá ocorrer quando um novo setup válido for formado.

---

# 25. Máquina de Estados

Cada ativo deve possuir um estado persistente.

Estados:

```text
NO_SETUP
WATCHING
TOUCHED_EMA
CONFIRMED
ALERT_SENT
INVALIDATED
COOLDOWN
```

Fluxo esperado:

```text
NO_SETUP
   ↓
TOUCHED_EMA
   ↓
WATCHING
   ↓
CONFIRMED
   ↓
ALERT_SENT
   ↓
COOLDOWN
```

---

# 26. Regras de Invalidação do Setup

Um ativo não pode permanecer indefinidamente no estado `WATCHING`.

O setup será invalidado quando qualquer uma das seguintes condições ocorrer:

### 26.1 Invalidação estrutural

No gráfico 4H:

```text
Close_4H < EMA50_4H
```

quando a EMA50 foi a zona de suporte utilizada.

Para setups baseados na EMA20, o sistema poderá utilizar:

```text
Close_4H < EMA50_4H
```

como limite estrutural mais amplo.

### 26.2 Perda do fundo do pullback

Se o preço romper o fundo que originou o setup:

```text
Close_4H < pullback_low
```

o setup será invalidado.

### 26.3 Timeout

Se não houver confirmação no 15m após determinado período:

```yaml
invalidation:
  max_15m_candles_without_confirmation: 16
```

Nesse exemplo:

```text
16 × 15 minutos = 4 horas
```

Após esse período, o setup volta para:

```text
NO_SETUP
```

### 26.4 Perda da condição macro

Se durante a vigilância o filtro principal deixar de ser válido:

```text
Close_1D <= EMA200_1D
```

o setup deve ser invalidado no próximo ciclo diário aplicável.

---

# 27. Transições da Máquina de Estados

```text
NO_SETUP
   ↓
TOUCHED_EMA
   ↓
WATCHING
   ├── confirmação 15m → CONFIRMED
   ├── timeout → INVALIDATED
   ├── perda do fundo → INVALIDATED
   └── perda estrutural → INVALIDATED

CONFIRMED
   ↓
ALERT_SENT
   ↓
COOLDOWN
   ↓
NO_SETUP
```

Nenhum estado deve permanecer indefinidamente sem uma regra de saída.

---

# 28. Telegram

Quando todos os critérios forem satisfeitos, o bot envia:

```text
🟢 SETUP CONFIRMADO

Ativo: BTC
Setup: Pullback EMA50
Timeframe: 4H
Confirmação: 15m

Tendência 1D:
Preço > EMA200
EMA200 inclinada positivamente

Entrada: $XX.XXX
Stop: $XX.XXX
Take Profit: $XX.XXX

Risco: X%
Retorno potencial: X%
Risk/Reward: X.X

Saldo de referência: $1.000
Risco financeiro: $10
Posição sugerida: $200

Resistência relevante: $XX.XXX

Classificação do alvo:
FAIXA PREFERENCIAL

Status BTC:
Bullish

⚠️ Alerta baseado em critérios técnicos.
Não representa garantia de resultado.
```

Quando o retorno estiver abaixo da faixa preferencial:

```text
Classificação do alvo:
ABAIXO DA FAIXA PREFERENCIAL
```

mas ainda acima do `absolute_min_percent`.

---

# 29. Execução

O bot **não executa ordens automaticamente** nas primeiras versões.

Fluxo:

```text
Bot detecta setup
        ↓
Calcula entrada
        ↓
Calcula Stop
        ↓
Calcula resistência
        ↓
Calcula Take Profit
        ↓
Valida retorno mínimo
        ↓
Valida R/R
        ↓
Calcula posição simulada
        ↓
Envia Telegram
        ↓
Usuário analisa
        ↓
Usuário decide se compra
        ↓
Usuário configura as ordens na corretora
```

Integração com corretora poderá ser adicionada futuramente.

---

# 30. Backtesting

Antes de utilizar o sistema com capital real, todas as regras devem ser testadas historicamente.

O backtest deve considerar:

* candles históricos;
* EMA;
* ATR;
* entrada 4H/15m;
* Stop Loss;
* Take Profit;
* resistência;
* retorno mínimo;
* Risk/Reward;
* taxas da corretora;
* slippage;
* spread, quando disponível;
* cooldown;
* deduplicação;
* capital inicial;
* tamanho das posições;
* exposição simultânea.

O backtest deve utilizar exatamente a mesma lógica do sistema de produção.

---

# 31. Métricas

O sistema deve gerar pelo menos:

```text
Total de operações
Win Rate
Loss Rate
Profit Factor
Retorno acumulado
Retorno médio por operação
Maior ganho
Maior perda
Drawdown máximo
Sequência máxima de perdas
Risk/Reward médio
Expectancy
```

Também deve ser possível separar os resultados por:

```text
Ativo
EMA20 vs EMA50
Ano
Mês
Regime do BTC
Tipo de confirmação
Stop method
Faixa de retorno
```

---

# 32. Evitar Overfitting

Os parâmetros devem ser configuráveis, mas não excessivamente otimizados sobre um único período histórico.

O backtest deve ser dividido em:

```text
Período de desenvolvimento
Período de validação
Período de teste
```

Sempre que possível, utilizar:

```text
Out-of-sample
Walk-forward analysis
```

---

# 33. Configuração Inicial

```yaml
assets:
  - BTC
  - ETH
  - XRP
  - SOL
  - LINK
  - XLM
  - BCH
  - NEAR
  - UNI
  - LTC
  - AVAX

timeframes:
  macro: 1D
  setup: 4H
  confirmation: 15m

data:
  daily_initial_candles: 700

ema:
  periods:
    - 20
    - 50
    - 100
    - 200

atr:
  period: 14

macro:
  price_above_ema200: true
  ema200_slope_required: true
  slope_periods: 5
  ema20_above_ema50: true

market_filter:
  enabled: true
  reference_asset: BTC
  bearish_action: BLOCK
  cache_per_cycle: true

entry:
  allowed_emas:
    - 20
    - 50
  touch_threshold_percent: 1.0
  use_atr_distance: true

confirmation:
  timeframe: 15m
  candle_closed_only: true
  require_reversal: true

invalidation:
  max_15m_candles_without_confirmation: 16
  invalidate_below_pullback_low: true
  invalidate_below_ema50_4h: true

risk:
  stop_method: structure_atr
  atr_multiplier: 1.0
  min_risk_reward: 2.0
  max_risk_per_trade_percent: 1.0
  simulated_account_balance: 1000

target:
  absolute_min_percent: 3.0
  preferred_min_percent: 5.0
  preferred_max_percent: 10.0
  allow_above_preferred_range: true
  resistance_aware: true

exposure:
  max_open_signals: 3
  max_signals_per_day: 5
  max_correlated_exposure: 2

system:
  candle_closed_only: true
  cooldown_hours: 12
```

---

# 34. Arquitetura Conceitual

```text
Exchange API
     ↓
Market Data
     ↓
Data Processor
     ↓
Historical Warm-up
     ↓
Indicator Engine
     ↓
┌─────────────────────────────┐
│ Market Filter — BTC         │
│ Executado uma vez por ciclo │
└─────────────────────────────┘
     ↓
Macro Filter 1D
     ↓
Setup Detector 4H
     ↓
Pullback / EMA Zone
     ↓
15m Confirmation Engine
     ↓
Risk Engine
     ├── Stop
     ├── Resistance
     ├── Take Profit
     └── Risk/Reward
     ↓
Position Sizing
     ↓
Exposure Manager
     ↓
Signal Manager
     ↓
Telegram
```

---

# 35. Persistência

O sistema deve persistir pelo menos:

```text
Último candle processado
Estado de cada ativo
Último setup detectado
Último alerta enviado
Timestamp do cooldown
Preço do setup
EMA utilizada
Pullback Low
Entry
Stop
Take Profit
Risk/Reward
Timestamp de ativação do WATCHING
Quantidade de candles 15m restantes
```

Isso evita perda de estado em reinicializações do processo.

---

# 36. Cache do Market Filter

O filtro do mercado deve ser calculado uma única vez por ciclo.

Exemplo conceitual:

```python
market_status = evaluate_market_filter()

for asset in assets:
    evaluate_asset(asset, market_status)
```

O resultado poderá ser:

```python
market_status = {
    "bullish": True,
    "reference_asset": "BTC",
    "timestamp": "...",
}
```

Os ativos devem consultar esse resultado em memória.

Não deve ocorrer:

```text
BTC → consulta Market Filter
ETH → consulta Market Filter
XRP → consulta Market Filter
SOL → consulta Market Filter
...
```

quando todos os ativos utilizam exatamente a mesma condição de mercado.

O objetivo é reduzir:

* chamadas à API;
* latência;
* processamento duplicado;
* risco de inconsistência entre avaliações realizadas em momentos diferentes.

---

# 37. Logs

O sistema deve registrar cada decisão importante.

Exemplo:

```text
[INFO] Market Filter - BTC: PASS
[INFO] BTC - Macro filter: PASS
[INFO] BTC - 4H EMA50 touch detected
[INFO] BTC - 15m confirmation: PASS
[INFO] BTC - Stop calculated: 4.2%
[INFO] BTC - Resistance distance: 9.1%
[INFO] BTC - TP calculated: 8.4%
[INFO] BTC - Minimum return: PASS
[INFO] BTC - Risk/Reward: 2.0
[INFO] BTC - Position size: $200
[INFO] BTC - SIGNAL GENERATED
```

Quando um trade for descartado:

```text
[INFO] ETH - Setup detected
[INFO] ETH - Potential return: 2.4%
[INFO] ETH - Absolute minimum: 3.0%
[INFO] ETH - SIGNAL REJECTED
[INFO] ETH - Reason: return below absolute minimum
```

---

# 38. Princípio Fundamental

O bot não deve tentar prever o mercado.

Seu objetivo é identificar **configurações previamente definidas e testadas** que apresentem características estatísticas favoráveis.

A estratégia deve ser tratada como um conjunto de hipóteses testáveis:

```text
H1:
Ativos acima da EMA200 diária apresentam comportamento
favorável para operações de pullback.

H2:
Pullbacks na EMA20/EMA50 no gráfico 4H apresentam
vantagem estatística quando acompanhados de confirmação
no gráfico de 15 minutos.

H3:
Stops baseados em estrutura + ATR reduzem saídas causadas
por ruído de mercado em comparação com stops percentuais
fixos.

H4:
Filtros de mercado baseados no BTC reduzem sinais durante
regimes desfavoráveis.

H5:
A exigência de um Risk/Reward mínimo melhora a expectativa
do sistema quando comparada à utilização de um Take Profit
fixo.

H6:
A análise de resistência evita operações cujo potencial de
valorização seja incompatível com o risco assumido.

H7:
Um retorno mínimo absoluto reduz a geração de sinais de
curto prazo incompatíveis com o objetivo de Swing Trade.

H8:
A confirmação em 15m após um setup identificado em 4H
reduz o atraso de entrada sem deteriorar significativamente
a qualidade dos sinais.
```

Cada hipótese deve ser validada separadamente através de backtesting.

---

# 39. Evolução do Projeto

## V1 — Sistema Funcional Completo

A V1 já deve conter **toda a lógica necessária para gerar um alerta completo e testável**.

### Dados e indicadores

* Dados da exchange
* Warm-up histórico
* EMA20/50/100/200
* ATR

### Filtros

* Market Filter BTC
* Filtro macro 1D
* Filtro do ativo

### Setup

* Pullback 4H
* Detecção EMA20/EMA50
* Vigilância 15m
* Confirmação de reversão

### Gestão de Trade

* Stop Loss estrutural + ATR
* Detecção de resistência
* Take Profit dinâmico
* Retorno mínimo absoluto
* Faixa preferencial de 5–10%
* Risk/Reward
* Tamanho de posição simulado

### Controle

* Máquina de estados
* Regras de invalidação
* Timeout
* Deduplicação
* Cooldown
* Controle de exposição

### Alertas

* Telegram
* Entry
* Stop
* Take Profit
* R/R
* Retorno potencial
* Tamanho da posição simulada
* Motivo do sinal

### Observabilidade

* Logs
* Estado persistente
* Cache do Market Filter

---

## V2 — Backtesting e Validação

* Engine histórica
* Métricas
* Taxas
* Slippage
* Testes out-of-sample
* Walk-forward
* Comparação de parâmetros
* Análise de sensibilidade
* Comparação entre métodos de Stop
* Comparação entre confirmações 15m

---

## V3 — Inteligência Adicional

* Regime de mercado
* Correlação entre ativos
* Score estatístico
* Detecção avançada de resistência
* Ranking de setups
* Análise de volatilidade

---

## V4 — Paper Trading

Executar a estratégia em ambiente simulado em tempo real.

```text
Market Data
     ↓
Signal Engine
     ↓
Virtual Order
     ↓
Virtual Position
     ↓
Virtual Exit
     ↓
Performance
```

O objetivo é comparar o comportamento em tempo real com os resultados do backtest.

---

## V5 — Automação Opcional

Somente após validação suficiente:

```text
Exchange API
     ↓
Signal
     ↓
Risk Manager
     ↓
Order Manager
     ↓
Execução automática
```

A execução automática deve permanecer separada do mecanismo de geração de sinais.
