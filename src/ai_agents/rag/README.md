# RAG

Histórico de notícias em Postgres + pgvector p/ retrieval do council e `/dossier`.

## Estrutura

- `store.py` — `ingest_once(conn, cfg)`: RSS → parse → classify → insere novas → embeda NULLs em lotes de 50 → prune por retenção
- `embed.py` — `embed_texts()`, `embed_query()` via `google-genai` (`gemini-embedding-2`, `output_dimensionality=768`)
- `retrieve.py` — `retrieve(conn, cfg, asset, max_age_hours, top_k)` → `(snippets, mode)`

## Retrieval

- `vector`: `embedding <=> query` (cosseno), cutoff `min_similarity`, filtro por aliases, dedup por overlap de título, teto `max_headlines`.
- `sql` (fallback): `ILIKE` por alias + recência, quando o embedding da query falha ou o pgvector está fora.
- Ingest usa `task_type=RETRIEVAL_DOCUMENT`; busca usa `RETRIEVAL_QUERY`.

## Convenções

- Embedding nunca quebra ingest: falha em lote salva a linha com `embedding NULL` p/ backfill no próximo ciclo.
- Cada linha guarda `embedding_model` + `embedding_dim`; troca de modelo exige re-embed deliberado (vetores não são comparáveis).
- Coluna `vector(768)` + índice HNSW criados em `src/db.py` só com `ai.enabled: true` (`embedding_dim` do config).
- Calibrar thresholds com `scripts/rag_probe.py ASSET` antes de confiar nos cutoffs.
