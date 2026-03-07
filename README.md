# graphrag-search

Production-ready scaffold on Python 3.11 with FastAPI, OpenSearch, Neo4j.

## Run

```bash
docker compose up --build
```

Or full stack with API:

```bash
docker compose -f docker-compose.integration.yml up --build
```

For local `sentence-transformers` embeddings, set in `.env`:

```dotenv
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384
EMBEDDING_DEVICE=cpu
EMBEDDING_NORMALIZE=true
EMBEDDING_PRELOAD_ON_STARTUP=true
LEXICAL_CANDIDATE_SIZE=40
VECTOR_CANDIDATE_SIZE=60
```

On first run, model files will be downloaded from Hugging Face.  
If you need fully offline mode, switch to:

```dotenv
EMBEDDING_PROVIDER=hash
```

For Ollama embeddings (recommended for this prototype), run Ollama and set:

```dotenv
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=qwen3-embedding:latest
EMBEDDING_DIMENSION=1024
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_ENDPOINT=/api/embed
OLLAMA_EMBEDDING_LEGACY_ENDPOINT=/api/embeddings
```

For LLM answering via Ollama, set:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=deepseek-r1:14b
LLM_BASE_URL=http://localhost:11434
LLM_OLLAMA_GENERATE_ENDPOINT=/api/generate
LLM_TIMEOUT_SECONDS=120
LLM_TEMPERATURE=0.2
LLM_PRELOAD_ON_STARTUP=false
```

Then pull both embedding and LLM models:

```bash
make infra-up
make ollama-pull-models
```

## API

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/documents`
- `POST /v1/documents/bulk`
- `POST /v1/search`
- `POST /v1/ask`
- `GET /ui` (browser debug frontend)

Index document example:

```json
{
  "id": "movie-1",
  "document": {
    "rating": 1,
    "movie": "Inception",
    "year": 2010,
    "country": "USA",
    "rating_ball": 8.8,
    "overview": "Dreams inside dreams.",
    "director": "Christopher Nolan",
    "screenwriter": "Christopher Nolan",
    "actors": "Leonardo DiCaprio",
    "url_logo": "https://example.com/logo.jpg"
  }
}
```

Search request example:

```json
{
  "query": "example",
  "limit": 10,
  "lexical_weight": 0.6,
  "vector_weight": 0.4
}
```

Each search result contains `debug` with per-channel (`lexical`/`vector`) raw and weighted scores.
Search results are also enriched with graph context from Neo4j in `payload.graph`.

Ask request example (LLM answer from search output):

```json
{
  "question": "Посоветуй фильм про космос",
  "items": [
    {
      "source": "opensearch",
      "id": "movie-30",
      "score": 0.91,
      "payload": {
        "movie": "ВАЛЛ·И",
        "overview": "..."
      },
      "debug": {}
    }
  ]
}
```

`POST /v1/ask` response includes:
- `answer`: plain text answer
- `think`: optional model reasoning/debug text (if model returned `<think>...</think>`)

Bulk indexing request example:

```json
{
  "items": [
    {
      "id": "movie-1",
      "document": {
        "movie": "Inception",
        "overview": "Dreams inside dreams."
      }
    },
    {
      "id": "movie-2",
      "document": {
        "movie": "Interstellar",
        "overview": "Space travel and time dilation."
      }
    }
  ]
}
```

## Tests

```bash
pytest
```

## Data Ingestion Script

- JSONL ingestion script: `app/domains/movies/scripts/ingest_movies_jsonl.py`
- Default input file: first `*.jsonl` from:
  - `app/domains/$DOMAIN_NAME/example_data/`
  - fallback: `app/domains/$DOMAIN_NAME/data/`

Run:

```bash
make ingest-domain-data DOMAIN_NAME=movies
```

Optional explicit dataset path for both commands:

```bash
make ingest-domain-data DOMAIN_NAME=movies DATASET_FILE=app/domains/movies/example_data/kinopoisk-top250.jsonl
```

## Domain Config And Templates

- Index config: `app/domains/movies/index_config.json`
- Lexical mustache template: `app/domains/movies/templates/lexical_search.mustache`
- Vector mustache template: `app/domains/movies/templates/vector_search.mustache`
- Graph context cypher template: `app/domains/movies/templates/graph_context.cypher.mustache`
- LLM answer prompt template: `app/domains/movies/templates/llm_answer_prompt.mustache`

These artifacts are loaded during startup, and startup logs include loaded domain name and template metadata.
