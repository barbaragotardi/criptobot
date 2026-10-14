# Revisar: guard de números do LLM (`sanitize_text`)

**Contexto:** após mover a sanitização para validadores Pydantic em `src/ai_agents/schemas.py`
(`sanitize_text` + `@field_validator` em `NewsView.rationale` e `Briefing.bullets`).
Garantia atual: **nenhum dígito/`$`/`%` vaza**, exceto whitelist intencional
(`EMA\d+`, `1D/4H/15m`, `Web3`, `L1/L2`, `Layer 2`, `ERC/BRC/BEP/TRC-20`, `Top N`).
Prompt tenta evitar, código garante.

## Pendências / imperfeições conhecidas

### 1. Preposições/artigos órfãos no meio de frase
- Ex: `"alta de 12.5% no dia"` → `"alta de no dia"`; `"rompeu os $67.5k com força"` → `"rompeu os com força"`.
- A limpeza de órfãs só atua no **fim de frase ou antes de pontuação** (proposital: mexer no meio
  exigiria NLP ou lista agressiva com risco de mutilar texto legítimo).
- Numericamente limpo, gramaticalmente imperfeito. Aceito como tradeoff.

### 2. Magnitude qualitativa sem dígito não é pega
- Ex: `"subiu muito"`, `"disparou"`, `"derreteu"` — sem dígito, o regex não atua; só o prompt segura.
- Uma denylist de adjetivos (`muito|disparou|...`) foi considerada e **rejeitada** (overblocking em pt-BR).
- Se vazar tom sensacionalista com frequência, reconsiderar — mas com lista mínima e métrica antes.

### 3. `council_once.py --fake` não rodado nesta máquina
- `scripts/sanity_check.py`: OK. Matriz de 10 casos do `sanitize_text`: OK.
- `council_once.py` exige Postgres (`db` host não resolve fora do compose) — ficou pendente.

### 4. Whitelist precisa de manutenção eventual
- Novos padrões de token (ex: outro `*-20`, `Layer 3`, `Web5`) quebram do mesmo jeito que `Web3` quebrava.
- `Top N` preserva dígitos **intencionalmente** (ranking, não preço) — documentado, mas revisitar se confundir.
- Placeholder usa letras `A–Z` (máx. 26 tokens por texto); impossível estourar em 140 chars, mas não é à prova de bala.

### 5. Defesa em profundidade em `format_council` ficou fora de escopo
- `src/alerts/telegram.py:format_council` confia no schema. Se surgir outro caminho que renderize
  `Briefing`/`NewsView`, o guard continua valendo (está no schema), mas um filtro last-mile no Telegram
  seria cinto + suspensórios. Decisão consciente de não fazer agora (mudança mínima).

### 6. `has_number()` / `strip_numbered()` em `llm.py` viraram detector sem caller
- Mantidos para log/métrica futura, mas hoje ninguém chama. Decidir: instrumentar ou remover.

## Checklist

1. **Rodar council com DB de pé:**
   - `make up` → `poetry run python scripts/council_once.py --asset BTC --fake` + 1 chamada real no Haiku.
   - Conferir `council_reports.briefing_json`: sem dígitos fora da whitelist.
2. **Amostrar briefings reais (1–2 semanas):**
   - `SELECT briefing_json FROM council_reports WHERE ok=1 ORDER BY ts DESC LIMIT 20;`
   - Classificar problemas: (a) número vazado, (b) órfã no meio, (c) tom sensacionalista sem dígito.
   - Só mexer no código se (a) > 0 ou (c) for frequente.
3. **Se (b) incomodar de verdade:** prototipar colapso de preposições empilhadas
   (`\b(de|em|para|...)\b(?=\s+(de|em|no|na|para|...)\b)`) em loop, com antes/depois em corpus real.
4. **Decidir destino de `has_number`/`strip_numbered`:** usar em log ou deletar.

## Feito quando

- [ ] `council_once.py --fake` + 1 chamada real verificados com DB de pé
- [ ] Amostra de briefings classificada em (a)/(b)/(c)
- [ ] Decisão registrada: manter como está, ou issue aberta para o item correspondente
- [ ] `has_number`/`strip_numbered`: instrumentados ou removidos
