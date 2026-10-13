.PHONY: help up update restart-app build-app rebuild-app logs logs-app logs-db ps health psql backup restore sanity dry-run paper-report install run check-config down

# Robit — atalhos docker compose v2.
# Dados vivem no volume nomeado pgdata: NENHUM alvo usa -v/volume rm.
# Só-config (config/*.yaml) -> make restart-app (sem rebuild).
# Código .py -> make update (rebuild só do app, db intocado).

help: ## Lista os comandos
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

check-config: ## Valida .env + config/config.yaml (falha alto antes do up)
	test -f .env || (echo "Falta .env (cp .env.example .env)" && exit 1)
	test -f config/config.yaml || (echo "Falta config/config.yaml" && exit 1)
	poetry run python -c "from src.config import load_config; load_config(); print('config OK')"

up: check-config ## Sobe db+app (cria pgdata se não existir)
	docker compose up -d

update: ## Deploy de código: rebuild só do app (cache) + recria só app
	docker compose build app
	docker compose up -d --no-deps app

restart-app: ## Aplica mudança só-config, sem rebuild
	docker compose restart app

build-app: ## Rebuild isolado da imagem do app
	docker compose build app

rebuild-app: ## Rebuild sem cache (pyproject.lock/Dockerfile mudou)
	docker compose build --no-cache app

logs: ## Últimas 200 linhas + follow de tudo
	docker compose logs --tail=200 -f

logs-app: ## Logs do app com follow
	docker compose logs --tail=200 -f app

logs-db: ## Logs do banco com follow
	docker compose logs --tail=200 -f db

ps: ## Estado dos containers
	docker compose ps

health: ## db pg_isready + estado do app
	docker compose exec db pg_isready -U $${POSTGRES_USER:-robit}
	docker compose ps app

psql: ## Abre psql no db (ex: SELECT asset,state FROM asset_state ORDER BY asset;)
	docker compose exec db psql -U $${POSTGRES_USER:-robit} $${POSTGRES_DB:-robit}

backup: ## pg_dump online para data/backup_AAAA-MM-DD_HHMM.sql (sem parar nada)
	mkdir -p data
	docker compose exec -T db pg_dump -U $${POSTGRES_USER:-robit} $${POSTGRES_DB:-robit} > data/backup_$$(date +%F_%H%M).sql
	@ls -t data/backup_*.sql | head -1

restore: ## Restaura dump: make restore BACKUP_FILE=data/backup_....sql (app parado, db ligado)
	test -n "$(BACKUP_FILE)" || (echo "Uso: make restore BACKUP_FILE=data/backup_....sql" && exit 1)
	test -f "$(BACKUP_FILE)" || (echo "Arquivo não encontrado: $(BACKUP_FILE)" && exit 1)
	docker compose stop app
	docker compose exec -T db psql -U $${POSTGRES_USER:-robit} $${POSTGRES_DB:-robit} < "$(BACKUP_FILE)"
	docker compose start app

sanity: ## Sanity numérico local (não toca no compose)
	poetry run python scripts/sanity_check.py

dry-run: ## 1 ciclo dry-run contra Binance, só leitura (não envia nada)
	poetry run python scripts/dry_run_once.py

paper-report: ## Relatório paper trading (requer DATABASE_URL)
	poetry run python scripts/paper_report.py

install: ## Instala deps locais via Poetry
	poetry install

run: ## Roda bot local (loop contínuo; requer DATABASE_URL + .env)
	poetry run python main.py

down: ## Para containers SEM apagar volume (dados preservados; nunca usa -v)
	docker compose down
