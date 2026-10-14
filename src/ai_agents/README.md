# AI Agents

Camada qualitativa sobre o motor quantitativo: só roda após `SIGNAL`, nunca veta sinal nem recalcula números.

## Estrutura

- `council.py` — `run_council(asset, cfg, conn)`, `submit(asset, cfg)` (background, conexão própria)
- `agents.py` — `run_news()`, `run_risk()`, `run_chief()`, `run_diagnostician()` (prompts pt-BR, saída via schemas)
- `schemas.py` — `NewsView` (sentiment/confidence + `NewsTopic` catalysts/risks + `rationale` curta), `RiskView` (`RiskFlag` flags), `Briefing` (tone + bullets curtos), `AssetDiagnosis` (`Blocker`/`Watcher`); `SCHEMA_VERSION = 1`
- `llm.py` — `complete_structured()` via LiteLLM (Haiku, sem fallback), `log_call()`, guard de números
- `tracing.py` — Langfuse opt-in (`ai.observability.langfuse.enabled` + chaves no `.env`): callbacks do LiteLLM (custo/tokens) + spans explícitos; fail-open, nunca veta nem atrasa o alerta
- `context.py` — `setup_facts()`, `portfolio_facts()`, `command_allowed()` (fatos determinísticos, sem LLM)
- `diagnose.py` — `diagnose_text()` p/ `/analyze` (só leitura, sem writes)
- `rag/` — ingestão + retrieval de notícias (ver `rag/README.md`)

## Fluxo

`SIGNAL` → alerta original + `ALERT_SENT` (inalterados) → `submit` em thread → news + risk em paralelo → chief → follow-up "🧠 Contexto IA" → `council_reports` + `ai_calls`.

## Convenções

- Fail-open: timeout, JSON inválido (após 1 repair retry), cooldown ou cap → loga e some, sem follow-up.
- LLM só escolhe categorias (enums impostos pelo schema; texto livre só em `rationale` e `bullets`, curtos e filtrados de `$`/`%`/dígitos longos); `evidence_ids` fora do conjunto são descartados. Números no Telegram vêm só dos facts do código (`telegram.py` renderiza enums por mapa fixo pt-BR).
- Desabilitado por padrão (`ai.enabled: false`); `submit` com IA off é no-op.
- Comandos: `/dossier` e `/analyze` via `listener.py`, com `validate_asset`, cooldown e cap diário.
