SHELL := /bin/bash

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn
DOCKER_COMPOSE ?= docker compose

APP_MODULE ?= app.main:app
APP_HOST ?= 0.0.0.0
APP_PORT ?= 8000
LOG_LEVEL ?= info

DOMAIN_NAME ?= movies
DATASET_FILE ?=

.PHONY: help install run ingest-domain-data test lint infra-up infra-down ha-up ha-down

help:
	@echo "Available targets:"
	@echo "  install        - Install Python dependencies"
	@echo "  run            - Run API locally from terminal"
	@echo "  ingest-domain-data  - Ingest DOMAIN_NAME JSONL via bulk API"
	@echo "  test           - Run pytest"
	@echo "  lint           - Run black checks"
	@echo "  infra-up       - Start OpenSearch + Neo4j (docker-compose.yml)"
	@echo "  infra-down     - Stop OpenSearch + Neo4j"
	@echo "  ha-up          - Start full HA stack (3 API replicas + nginx LB + OpenSearch + Neo4j + Prometheus + Grafana + Jaeger + cAdvisor + Locust)"
	@echo "  ha-down        - Stop full HA stack"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	curl -fsSL https://ollama.com/install.sh | sh

run:
	$(UVICORN) $(APP_MODULE) --host $(APP_HOST) --port $(APP_PORT) --log-level $(LOG_LEVEL)

ingest-domain-data:
	DOMAIN_NAME=$(DOMAIN_NAME) PYTHONPATH=. $(PYTHON) app/domains/movies/scripts/ingest_movies_jsonl.py $(if $(DATASET_FILE),--file $(DATASET_FILE),)

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m black .

infra-up:
	$(DOCKER_COMPOSE) up -d --wait

infra-down:
	$(DOCKER_COMPOSE) down

ha-up:
	$(DOCKER_COMPOSE) -f docker-compose.base.yml -f docker-compose.ha.yml --profile loadtest up -d --build
	$(MAKE) ingest-domain-data DOMAIN_NAME=$(DOMAIN_NAME) DATASET_FILE=$(DATASET_FILE)

ha-down:
	$(DOCKER_COMPOSE) -f docker-compose.base.yml -f docker-compose.ha.yml --profile loadtest down
