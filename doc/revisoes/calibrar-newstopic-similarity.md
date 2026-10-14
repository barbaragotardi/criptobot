# Revisar: calibrar NewsTopic + min_similarity

**Quando:** após alguns dias de ingestão contínua (`news-ingest` rodando) + uso de `/dossier`.
**Por quê:** a lista `NewsTopic` (12 códigos) e os cutoffs `min_similarity: 0.30` / `near_dup_similarity: 0.92` são chutes iniciais.

## Checklist

1. **Corpus tem volume?**
   - `make psql` → `SELECT COUNT(*), MIN(fetched_ts), MAX(fetched_ts) FROM news_articles;`
   - Esperar alguns dias de histórico antes de concluir qualquer coisa.

2. **Calibrar `min_similarity` / `near_dup_similarity`:**
   - `poetry run python scripts/rag_probe.py BTC` (e outros ativos com sinal).
   - Ajustar `config/config.yaml` → `ai.rag.min_similarity` / `near_dup_similarity` conforme os scores reais.

3. **Revisar cobertura do `NewsTopic`:**
   - Amostrar `/dossier` e `council_reports.news_json`: os tópicos reais estão caindo em `other` com frequência?
   - Códigos atuais: `regulation, etf_flows, hack_exploit, macro_rates, exchange_listing, partnership, protocol_upgrade, liquidations, adoption, legal, whale_activity, other`.
   - Se um tema novo aparece sempre → adicionar membro ao enum.

4. **Ao mudar o enum, mexer em 3 lugares juntos:**
   - `src/ai_agents/schemas.py` (`NewsTopic`)
   - `src/alerts/telegram.py` (`TOPIC_LABELS` — todo membro precisa de rótulo pt-BR)
   - `src/ai_agents/agents.py` (`TOPICS` no prompt do news)

5. **Verificação pós-mudança:**
   - `set(labels) == set(get_args(NewsTopic))`
   - `council_once.py --asset BTC --fake` + 1 chamada real no Haiku.

## Feito quando

- [ ] Corpus com vários dias verificado
- [ ] `rag_probe.py` rodado e cutoffs ajustados (ou mantidos com justificativa)
- [ ] Distribuição dos tópicos amostrada (`other` não domina)
- [ ] Enum/labels/prompt atualizados se necessário (ou decisão de manter)
