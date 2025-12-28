# hybrid-graphrag-search

Hybrid search prototype combining OpenSearch BM25 + vector retrieval with Neo4j graph expansions. FastAPI backend exposes ingestion and search APIs; services are placeholders ready for production logic.

## Prerequisites
- Docker + Docker Compose
- Python 3.11

## Setup
```bash
cp .env.example .env
make dev          # create venv and install deps
make up           # start OpenSearch + Neo4j + backend (add `--profile dashboards` for UI)
python -m hybrid_graphrag_search.cli.init_indices  # initialize OpenSearch index mapping
python -m hybrid_graphrag_search.cli.init_graph    # initialize Neo4j constraints/indexes
make run          # local FastAPI with reload (uses .venv)
```

## API
- `GET /health` – checks connectivity to OpenSearch and Neo4j
- `POST /api/ingest` – ingest a document (placeholder flow)
- `POST /api/search` – hybrid search (placeholder flow)

Example requests:
```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"doc-1","title":"Demo","text":"Sample text to chunk and index.","tags":["demo"]}'

# Batch ingest
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '[{"doc_id":"doc-2","title":"Second","text":"Another text"},{"doc_id":"doc-3","title":"Third","text":"More text"}]'

curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"sample query","top_k":5}'
```

## Makefile targets
- `make dev` – create virtualenv + install deps
- `make fmt` – format with ruff
- `make lint` – lint with ruff
- `make test` – run pytest
- `make up` / `make down` – docker-compose controls (include `--profile dashboards` to enable UI)
- `make reset` – teardown containers + remove data
- `make init-indices` / `make init-graph` – initialize OpenSearch mappings and Neo4j constraints
- `make ingest-sample` – ingest demo docs
- `make eval-sample` – run metrics on sample dataset

## Evaluation
- Dataset format: JSONL where each line is `{"query": "...", "relevant_chunk_ids": ["doc-1-chunk-0"], "relevant_doc_ids": ["doc-1"]}` (one of the relevance lists may be empty).
- Run: `python -m hybrid_graphrag_search.eval --dataset data/eval.jsonl --k 10 --out results.json`
- Prints a table for configs: BM25, Dense (placeholder), Hybrid (BM25+Dense), Hybrid+Graph.
- Sample dataset: `data/eval.sample.jsonl`

## Folder structure
```
src/hybrid_graphrag_search/
  api/           # FastAPI routes
  models/        # Pydantic schemas
  pipelines/     # Ingestion/search orchestration (placeholders)
  services/      # OpenSearch/Neo4j/embedding placeholders
  logging_config.py
  main.py
tests/           # Minimal unit tests
docker-compose.yml
pyproject.toml
```

## Notes
- Services and pipelines are placeholders—implement indexing, embedding, and graph operations before production use.
- Embedding model is intentionally not loaded in placeholder mode to avoid large downloads; wire it up in `api/routes.py` when ready.

## Troubleshooting
- OpenSearch failing health: ensure memory limits allow `memlock`, or reduce `OPENSEARCH_JAVA_OPTS` in `docker-compose.yml`. Check logs: `docker compose logs opensearch`.
- Neo4j auth errors: verify `NEO4J_USER`/`NEO4J_PASSWORD` match `.env`; re-run `make reset` to clear volumes for local dev.
- Backend health 503: confirm services are up (`make up`), initialize indices (`python -m hybrid_graphrag_search.cli.init_indices`) and graph schema (`python -m hybrid_graphrag_search.cli.init_graph`).
- Ingestion failures: check OpenSearch index exists and embedding model downloads successfully; retry after ensuring network access to pull models.
