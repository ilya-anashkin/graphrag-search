SHELL := /bin/bash

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn
DOCKER_COMPOSE ?= docker compose

APP_MODULE ?= app.main:app
APP_HOST ?= 0.0.0.0
APP_PORT ?= 8000
LOG_LEVEL ?= info
OPENSEARCH_BASE_URL ?= http://localhost:9200
NEO4J_URI ?= bolt://localhost:7687
EMBEDDING_PROVIDER ?= local
EMBEDDING_MODEL ?= sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION ?= 384
EMBEDDING_DEVICE ?= cpu
EMBEDDING_NORMALIZE ?= true
DOMAIN_NAME ?= movies
DOMAINS_ROOT ?= app/domains
LEXICAL_CANDIDATE_SIZE ?= 40
VECTOR_CANDIDATE_SIZE ?= 60

BASE_COMPOSE_FILE ?= docker-compose.yml
INTEGRATION_COMPOSE_FILE ?= docker-compose.integration.yml

.PHONY: help install run-local run-local-dev ingest-movies-data test lint format \
	infra-up infra-down infra-logs infra-ps \
	stack-up stack-down stack-logs stack-ps stack-rebuild

help:
	@echo "Available targets:"
	@echo "  install        - Install Python dependencies"
	@echo "  run-local      - Run API locally from terminal"
	@echo "  run-local-dev  - Run API locally with auto-reload"
	@echo "  ingest-movies-data - Ingest movies JSONL via bulk API"
	@echo "  test           - Run pytest"
	@echo "  lint           - Run ruff checks"
	@echo "  format         - Run ruff formatter"
	@echo "  infra-up       - Start OpenSearch + Neo4j (docker-compose.yml)"
	@echo "  infra-down     - Stop OpenSearch + Neo4j"
	@echo "  infra-logs     - Show infra logs"
	@echo "  infra-ps       - Show infra containers"
	@echo "  stack-up       - Start full stack including API"
	@echo "  stack-down     - Stop full stack"
	@echo "  stack-logs     - Show full-stack logs"
	@echo "  stack-ps       - Show full-stack containers"
	@echo "  stack-rebuild  - Rebuild and start full stack"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run-local:
	OPENSEARCH_BASE_URL=$(OPENSEARCH_BASE_URL) NEO4J_URI=$(NEO4J_URI) \
	EMBEDDING_PROVIDER=$(EMBEDDING_PROVIDER) EMBEDDING_MODEL=$(EMBEDDING_MODEL) \
	EMBEDDING_DIMENSION=$(EMBEDDING_DIMENSION) EMBEDDING_DEVICE=$(EMBEDDING_DEVICE) \
	EMBEDDING_NORMALIZE=$(EMBEDDING_NORMALIZE) DOMAIN_NAME=$(DOMAIN_NAME) DOMAINS_ROOT=$(DOMAINS_ROOT) \
	LEXICAL_CANDIDATE_SIZE=$(LEXICAL_CANDIDATE_SIZE) VECTOR_CANDIDATE_SIZE=$(VECTOR_CANDIDATE_SIZE) \
	$(UVICORN) $(APP_MODULE) --host $(APP_HOST) --port $(APP_PORT) --log-level $(LOG_LEVEL)

run-local-dev:
	OPENSEARCH_BASE_URL=$(OPENSEARCH_BASE_URL) NEO4J_URI=$(NEO4J_URI) \
	EMBEDDING_PROVIDER=$(EMBEDDING_PROVIDER) EMBEDDING_MODEL=$(EMBEDDING_MODEL) \
	EMBEDDING_DIMENSION=$(EMBEDDING_DIMENSION) EMBEDDING_DEVICE=$(EMBEDDING_DEVICE) \
	EMBEDDING_NORMALIZE=$(EMBEDDING_NORMALIZE) DOMAIN_NAME=$(DOMAIN_NAME) DOMAINS_ROOT=$(DOMAINS_ROOT) \
	LEXICAL_CANDIDATE_SIZE=$(LEXICAL_CANDIDATE_SIZE) VECTOR_CANDIDATE_SIZE=$(VECTOR_CANDIDATE_SIZE) \
	$(UVICORN) $(APP_MODULE) --host $(APP_HOST) --port $(APP_PORT) --log-level $(LOG_LEVEL) --reload

ingest-movies-data:
	$(PYTHON) scripts/ingest_movies_jsonl.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

infra-up:
	$(DOCKER_COMPOSE) -f $(BASE_COMPOSE_FILE) up -d --wait

infra-down:
	$(DOCKER_COMPOSE) -f $(BASE_COMPOSE_FILE) down

infra-logs:
	$(DOCKER_COMPOSE) -f $(BASE_COMPOSE_FILE) logs -f

infra-ps:
	$(DOCKER_COMPOSE) -f $(BASE_COMPOSE_FILE) ps

stack-up:
	$(DOCKER_COMPOSE) -f $(INTEGRATION_COMPOSE_FILE) up -d

stack-down:
	$(DOCKER_COMPOSE) -f $(INTEGRATION_COMPOSE_FILE) down

stack-logs:
	$(DOCKER_COMPOSE) -f $(INTEGRATION_COMPOSE_FILE) logs -f

stack-ps:
	$(DOCKER_COMPOSE) -f $(INTEGRATION_COMPOSE_FILE) ps

stack-rebuild:
	$(DOCKER_COMPOSE) -f $(INTEGRATION_COMPOSE_FILE) up -d --build
