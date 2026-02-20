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

For local embeddings (prototype mode), set in `.env`:

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

## API

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/documents`
- `POST /v1/documents/bulk`
- `POST /v1/search`

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
  ],
  "batch_size": 50
}
```

## Tests

```bash
pytest
```

## Data Ingestion Script

- JSONL ingestion script: `scripts/ingest_movies_jsonl.py`
- Default input file: `app/domains/movies/example_data/kinopoisk-top250.jsonl`

Run:

```bash
make ingest-movies-data
```

## Domain Config And Templates

- Index config: `app/domains/movies/index_config.json`
- Lexical mustache template: `app/domains/movies/templates/lexical_search.mustache`
- Vector mustache template: `app/domains/movies/templates/vector_search.mustache`

These artifacts are loaded during startup, and startup logs include loaded domain name and template metadata.
