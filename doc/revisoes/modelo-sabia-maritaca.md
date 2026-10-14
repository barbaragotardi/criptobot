# Revisar: modelo Sabiá (Maritaca) como opção ao Haiku

**Contexto:** hoje o único modelo de chat é `anthropic/claude-haiku-4-5-20251001` via
LiteLLM (`config/config.yaml` → `ai.model`, chave `ANTHROPIC_API_KEY`). Para texto em
português (principalmente após o agente tradutor de `prompts-ingles-tradutor.md`),
queremos poder trocar para um modelo Sabiá da Maritaca.
Ref: https://docs.maritaca.ai/pt/api/openai-compatibilidade

## O que a doc da Maritaca garante

- Endpoint **Chat Completions compatível com OpenAI**: `POST https://chat.maritaca.ai/api/chat/completions`
  com `Authorization: Bearer MARITACA_API_KEY`, `messages`, `max_tokens` — mesmo formato
  da OpenAI. É esse endpoint que o LiteLLM precisa (não o Responses API).
- Modelos: `sabia-4` (atual; checar `/pt/modelos` na hora de implementar — nomes mudam).
- Há também páginas de **saídas estruturadas** e **chamada de funções** — ler antes, pois
  o pipeline depende de `response_format` com JSON schema (ver risco 1).

## Proposta

Tudo via config, sem hardcode (regra do projeto). Desenho sugerido no bloco `ai:`:

```yaml
ai:
  model: "sabia-4"                      # antes: "anthropic/claude-haiku-4-5-20251001"
  provider:
    api_base: "https://chat.maritaca.ai/api"  # LiteLLM OpenAI-compatible endpoint
    api_key_env: "MARITACA_API_KEY"            # nome da var no .env (nunca o valor)
```

`llm.py` resolveria `api_base`/`api_key` a partir daí e repassaria ao
`litellm.completion` (que aceita `api_base`/`api_key` por chamada para providers
OpenAI-compatible). `.env.example` ganha `MARITACA_API_KEY=`.

## Riscos / pontos a verificar antes (na ordem)

1. **Structured output é o gating item.** O pipeline exige
   `litellm.supports_response_schema(model)` + `response_format={"type": "json_object",
   "response_schema": ...}`. Testar primeiro com `scripts/smoke_ai.py` adaptado (custo
   mínimo): se o Sabiá não honrar o schema, a opção morre aqui — sem mexer no resto.
   Ler também a página de saídas estruturadas da Maritaca antes do teste.
2. **Custo zerado nos logs.** `litellm.completion_cost()` provavelmente não conhece a
   tabela de preços do Sabiá → `ai_calls.cost_usd = 0` e custo ausente no Langfuse.
   Decidir na implementação: aceitar temporariamente, ou configurar preço manual no
   LiteLLM, ou estimar — mas nunca inventar número silenciosamente.
3. **Qualidade dos enums.** O contrato do projeto é "LLM só escolhe categorias" —
   comparar 1–2 councils Haiku vs Sabiá no mesmo setup (mesmas notícias/fatos) e checar
   aderência aos códigos + `repair retry` rate em `ai_calls`.
4. **Latência/timeout.** `ai.timeout_s: 40` pode precisar de ajuste por provider; se for
   por modelo, o campo vai para o bloco do provider, não solto.
5. **Troca é global ou por agente?** Começar global (`ai.model` único, como hoje).
   Por-agente (ex: Sabiá só no tradutor, Haiku no resto) é extensão futura explícita,
   não parte desta revisão.
6. **Fora de escopo:** trocar embeddings Gemini por Maritaca (há doc de embeddings+RAG;
   anotar como ideia futura, não fazer junto).

## Checklist

1. Ler páginas de modelos + saídas estruturadas da Maritaca; anotar nome exato do modelo.
2. Spike sem custo de design: `smoke_ai` adaptado com `api_base`/`api_key` → confirmar
   `supports_response_schema` + 1 chamada com schema real.
3. Implementar `ai.provider` em `llm.py` (fail-open mantido; sem provider = Anthropic
   como hoje); `MARITACA_API_KEY` no `.env.example`.
4. Rodar `scripts/council_once.py --asset BTC` com cada modelo; comparar enums, retries,
   latência e custo (Langfuse + `ai_calls`).
5. Docs (`README` seção LLMOps, `CONTEXT.md`, `src/ai_agents/README.md`).

## Feito quando

- [ ] Spike de structured output com Sabiá: passa ou a opção é descartada com motivo registrado
- [ ] Troca Haiku ↔ Sabiá só via `config.yaml` + `.env` (nenhum hardcode, nenhum `if maritaca` espalhado)
- [ ] Decisão sobre custo (real, estimado ou ausente documentado) registrada aqui
- [ ] 1 council real por modelo comparado (enums + retries + latência)
- [ ] Docs atualizados
