# Confirmation

Confirmação 15m com candles fechados (`confirm.py`).

## Funções

- `confirm(df_15m, method, ema_value=None)` — despacha pelo método, retorna `(ok, motivo)`
- `confirm_reversal(df_15m)` — engolfo de alta OU fechamento acima da máxima anterior
- `confirm_ema_reclaim(df_15m, ema_value)` — fechamento 15m de volta acima da EMA tocada

## Métodos (`method`)

- `reversal` (padrão) — só `confirm_reversal`
- `ema_reclaim` — só `confirm_ema_reclaim`
- `any` — OR dos dois (tenta reversão, senão EMA reclaim)

## Notas

- Assume candles **fechados** (o chamador descarta o candle em aberto)
- Usado após pullback 4H detectado (estado WATCHING)
- Método configurável em `config/config.yaml`
