# Exposure

Limites de exposição de sinais.

## Módulos

- `manager.py` — `exposure_ok()`, `record_signal()`

## Funções

- `exposure_ok(conn, asset, cfg, now=None)` → `(ok, motivo)`: checa tetos antes de aceitar sinal
- `record_signal(conn, now=None)` → registra sinal do dia (estatística)

## Configuração

Via `config/config.yaml`:
```yaml
exposure:
  max_open_signals: 15
  max_signals_per_day: 10
  max_correlated_exposure: 15
```

## Notas

- `now` explícito serve p/ testes; produção passa `None` (= wall clock)
- Limites raramente ligam em prática
