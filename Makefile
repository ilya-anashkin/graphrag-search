SHELL := /bin/bash

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn
DOCKER_COMPOSE ?= docker compose

APP_MODULE ?= app.main:app
APP_HOST ?= 0.0.0.0
APP_PORT ?= 8000
LOG_LEVEL ?= info

GRAPH_INGEST_BATCH_SIZE=100

.PHONY: help install run-local ingest-movies-data ingest-movies-graph ollama-pull-models test lint format \
	infra-up infra-down

help:
	@echo "Available targets:"
	@echo "  install        - Install Python dependencies"
	@echo "  run-local      - Run API locally from terminal"
	@echo "  ingest-movies-data - Ingest movies JSONL via bulk API"
	@echo "  ingest-movies-graph - Ingest movies JSONL into Neo4j graph"
	@echo "  test           - Run pytest"
	@echo "  lint           - Run ruff checks"
	@echo "  format         - Run ruff formatter"
	@echo "  infra-up       - Start OpenSearch + Neo4j (docker-compose.yml)"
	@echo "  infra-down     - Stop OpenSearch + Neo4j"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	curl -fsSL https://ollama.com/install.sh | sh

run-local:
	$(UVICORN) $(APP_MODULE) --host $(APP_HOST) --port $(APP_PORT) --log-level $(LOG_LEVEL)

ingest-movies-data:
	PYTHONPATH=. $(PYTHON) scripts/ingest_movies_jsonl.py

ingest-movies-graph:
	PYTHONPATH=. $(PYTHON) scripts/ingest_movies_graph.py --batch-size $(GRAPH_INGEST_BATCH_SIZE)

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

infra-up:
	$(DOCKER_COMPOSE) up -d --wait

infra-down:
	$(DOCKER_COMPOSE) down
