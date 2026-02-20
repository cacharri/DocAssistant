.PHONY: help up down rebuild logs ps ingest index test reset db psql

help:
	@echo "Targets:"
	@echo "  make up        -> docker compose up -d --build"
	@echo "  make down      -> docker compose down"
	@echo "  make rebuild   -> rebuild api image"
	@echo "  make logs      -> tail api logs"
	@echo "  make ps        -> docker compose ps"
	@echo "  make ingest    -> run ingestion"
	@echo "  make index     -> build FAISS index"
	@echo "  make test      -> run pytest"
	@echo "  make reset     -> nuke volumes + rebuild"
	@echo "  make psql      -> open psql shell"
	@echo "  make db        -> show doc/chunk counts"

up:
	docker compose up -d --build

down:
	docker compose down

rebuild:
	docker compose build --no-cache api

logs:
	docker logs -f docassistant-api --tail 200

ps:
	docker compose ps

ingest:
	docker compose run --rm api python -m app.ingest.ingest

index:
	docker compose run --rm api python -m app.retrieval.build_index

test:
	docker compose run --rm api pytest -q

reset:
	docker compose down -v
	docker compose up -d --build

psql:
	docker exec -it docassistant-postgres psql -U docassistant -d docassistant

db:
	docker exec -it docassistant-postgres psql -U docassistant -d docassistant -c "SELECT doc_type, count(*) FROM documents GROUP BY doc_type;"
	docker exec -it docassistant-postgres psql -U docassistant -d docassistant -c "SELECT count(*) FROM chunks;"

eval:
	docker compose run --rm api python -m app.eval.retrieval_eval --k 5
