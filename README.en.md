# graphrag-search

Russian version: `README.md`

Hybrid search system built with `FastAPI`, `OpenSearch`, `Neo4j`, and `Ollama`.

What is included:
- hybrid search: `lexical`, `lexical_vector`, `lexical_vector_graph`
- graph-based result enrichment through `Neo4j`
- LLM answer generation from retrieved documents
- browser debug UI
- HA and load testing stack

## Stack

- `FastAPI`
- `OpenSearch`
- `Neo4j`
- `Ollama`
- `Prometheus`
- `Grafana`
- `Jaeger`
- `Locust`

## Configuration

Main files:
- `.env.example` — example configuration
- `.env` — local settings
- `.env.docker` — container override

Default domain: `movies`.

## Local Run

1. Start infrastructure:

```bash
make infra-up
```

2. Start the API:

```bash
make run
```

3. Load data:

```bash
make ingest-domain-data DOMAIN_NAME=movies
```

If you need a larger dataset:

```bash
make ingest-domain-data-expanded DOMAIN_NAME=movies DATASET_MULTIPLIER=10
```

## HA and Load Testing

Start the full stack:

```bash
make ha-up
```

Stop it:

```bash
make ha-down
```

Services:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- UI: `http://localhost:8000/ui`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- Locust: `http://localhost:8089`

## Main API Endpoints

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/documents`
- `POST /v1/documents/bulk`
- `POST /v1/search`
- `POST /v1/ask`

Search request example:

```json
{
  "query": "space movies",
  "limit": 10,
  "search_mode": "lexical_vector_graph",
  "lexical_weight": 0.6,
  "vector_weight": 0.4
}
```

Supported `search_mode` values:
- `lexical`
- `lexical_vector`
- `lexical_vector_graph`

## Domain Structure

Each domain uses files in `app/domains/<domain_name>/`:
- `index_config.json`
- `templates/lexical_search.mustache`
- `templates/vector_search.mustache`
- `templates/graph_context.cypher.mustache`
- `templates/graph_ingest.cypher.mustache`
- `templates/llm_answer_prompt.mustache`

## Tests

```bash
make test
```
