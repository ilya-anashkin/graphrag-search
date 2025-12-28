PYTHON := python3.11
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate

.PHONY: dev test fmt lint up down reset run init-indices init-graph ingest-sample eval-sample

dev:
	@$(PYTHON) -m venv $(VENV)
	@$(ACTIVATE) && pip install --upgrade pip
	@$(ACTIVATE) && pip install -e .[dev]

test:
	@$(ACTIVATE) && pytest

fmt:
	@$(ACTIVATE) && ruff format src tests
	@$(ACTIVATE) && black src tests
	@$(ACTIVATE) && isort src tests

lint:
	@$(ACTIVATE) && ruff check src tests

run:
	@$(ACTIVATE) && uvicorn hybrid_graphrag_search.main:app --host 0.0.0.0 --port 8000 --reload

init-indices:
	@$(ACTIVATE) && python -m hybrid_graphrag_search.cli.init_indices

init-graph:
	@$(ACTIVATE) && python -m hybrid_graphrag_search.cli.init_graph

ingest-sample:
	@$(ACTIVATE) && python scripts/ingest_sample.py

eval-sample:
	@$(ACTIVATE) && python -m hybrid_graphrag_search.eval --dataset data/eval.sample.jsonl --k 5

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down -v
	rm -rf data
