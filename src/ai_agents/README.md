# AI Agents

Camada qualitativa sobre o motor quantitativo: só roda após `SIGNAL`, nunca veta sinal nem recalcula números.

## Estrutura

- `council.py` — `run_council(asset, cfg, conn)`, `submit(asset, cfg)` (background, conexão própria)
- `agents.py` — `run_news()`, `run_risk()`, `run_chief()`, `run_diagnostician()` (prompts pt-BR, saída via schemas)
- `schemas.py` — `NewsView`, `RiskView`, `Briefing`, `AssetDiagnosis` (`SCHEMA_VERSION = 1`)
- `llm.py` — `complete_structured()` via LiteLLM (Haiku, sem fallback), `log_call()`, guard de números
- `context.py` — `setup_facts()`, `portfolio_facts()`, `command_allowed()` (fatos determinísticos, sem LLM)
- `diagnose.py` — `diagnose_text()` p/ `/analyze` (só leitura, sem writes)
- `rag/` — ingestão + retrieval de notícias (ver `rag/README.md`)

## Fluxo

`SIGNAL` → alerta original + `ALERT_SENT` (inalterados) → `submit` em thread → news + risk em paralelo → chief → follow-up "🧠 Contexto IA" → `council_reports` + `ai_calls`.

## Convenções

- Fail-open: timeout, JSON inválido (após 1 repair retry), cooldown ou cap → loga e some, sem follow-up.
- LLM nunca emite números (`$`, `%`, dígitos longos são filtrados); `evidence_ids` fora do conjunto são descartados.
- Desabilitado por padrão (`ai.enabled: false`); `submit` com IA off é no-op.
- Comandos: `/dossier` e `/analyze` via `listener.py`, com `validate_asset`, cooldown e cap diário.
