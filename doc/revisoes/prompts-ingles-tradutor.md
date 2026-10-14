# Revisar: prompts em inglês + agente tradutor configurável

**Contexto:** prompts dos agentes em `src/ai_agents/agents.py` hoje são pt-BR
(`NEWS_SYS`, `RISK_SYS`, `CHIEF_SYS`, `DIAG_SYS`), mas o `rationale` do council real
de BTC veio em inglês ("Mixed signals with regulatory headwinds...") apesar do prompt
pedir pt-BR. Hipótese: Haiku (e LLMs em geral) seguem instruções de formato melhor em
inglês; forçar o idioma de saída no mesmo prompt que impõe o schema JSON enfraquece
ambas as restrições. Proposta: **raciocinar em inglês, traduzir no fim**.

## Proposta

1. Reescrever os 4 system prompts para inglês US (enums e códigos permanecem os mesmos —
   são identificadores, não texto).
2. Novo agente `translator`, rodando **depois** do chief (council) e **depois** do
   diagnostician onde houver texto livre (hoje: só `rationale` + `bullets`; `RiskView`,
   `AssetDiagnosis` e flags são enums, nada a traduzir).
3. Config em `config/config.yaml`, bloco `ai:`:
   ```yaml
   ai:
     language: ""  # "" = mantém inglês US; ex: "pt-BR"
   ```
   Sem chave ou blank → sem chamada extra, texto sai em inglês.
4. Schema Pydantic próprio (`TranslatedBriefing`: `rationale`, `bullets`), validado igual
   aos demais; texto traduzido passa pelo guard de números **de novo**
   (`strip_numbered`, pois a tradução pode reintroduzir `$`/`%`/dígitos longos).

## Implicações / riscos

1. **+1 chamada LLM por council e por `/analyze`** (quando `language` setado): conta no
   `max_calls_per_day`, soma custo (visível no Langfuse como generation `translator`) e
   adiciona latência — aceitável porque council e `/analyze` já rodam em background.
2. **Fail-open obrigatório:** se o tradutor falhar (timeout, JSON inválido após 1 retry),
   envia o original em inglês, loga em `ai_calls` com `ok=0` e segue. Nunca bloqueia o
   alerta nem o follow-up.
3. **Tradução não recalcula nada:** entrada é só `rationale` + `bullets` (texto curto,
   sem números por construção); enums, fatos e números do Telegram continuam vindo do
   código. Auditoria no Langfuse mostra generation `translator` com input EN → output
   traduzido.
4. **`/dossier` fora de escopo:** não chama LLM hoje (só retrieval); nada a traduzir.
5. **Idiomas suportados:** começar com allowlist mínima (`pt-BR`); qualquer outro valor
   deve falhar loud no `load_config`/validação (não adivinhar idioma).

## Checklist

1. Reescrever `NEWS_SYS`/`RISK_SYS`/`CHIEF_SYS`/`DIAG_SYS` para inglês US, mantendo os
   códigos de enum byte-igualmente.
2. Criar `run_translator(conn, cfg, rationale, bullets, lang)` em `agents.py` +
   schema em `schemas.py`; plugar em `council.py` (pós-chief) e `listener.py`
   (`/analyze`, se um dia tiver texto livre — hoje é no-op documentado).
3. Reaplicar `strip_numbered` pós-tradução; cobrir com Langfuse (generation `translator`
   filha do trace existente via `_trace`).
4. Documentar `ai.language` no `README.md` (seção LLMOps) e `CONTEXT.md`.
5. Validar: 1 council real + 1 `/analyze` com `language: "pt-BR"` e com `""`;
   conferir idioma, guard de números e custo extra no Langfuse.

## Feito quando

- [ ] Prompts em inglês sem mudar nenhum código de enum (diff revisado)
- [ ] `ai.language: "pt-BR"` traduz `rationale`+`bullets`; `""` mantém inglês sem chamada extra
- [ ] Falha do tradutor entrega o inglês original (teste com chave inválida temporária)
- [ ] Nenhum dígito/`$`/`%` no texto final em ambos os idiomas (amostra real)
- [ ] Docs (`README`, `CONTEXT`) atualizados
