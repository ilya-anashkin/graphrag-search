# graphrag-search

Гибридная поисковая система с GraphRAG и LLM-ответом поверх доменной конфигурации.

Стек:
- `FastAPI`
- `OpenSearch`
- `Neo4j`
- `Ollama` для embeddings и LLM
- `Prometheus`, `Grafana`, `Jaeger`, `Locust` для наблюдаемости и нагрузочного тестирования

## Что умеет

- индексировать документы в `OpenSearch` и граф в `Neo4j`
- выполнять гибридный поиск: lexical + vector
- обогащать выдачу графовым контекстом
- строить LLM-ответ по результатам поиска
- работать в HA-режиме: `3` копии API + `nginx` round-robin

## Доменная модель

Проект доменно-конфигурируемый. Активный домен задается через `DOMAIN_NAME`.

Для домена должны быть определены артефакты в `app/domains/<domain_name>/`:
- `index_config.json`
- `templates/lexical_search.mustache`
- `templates/vector_search.mustache`
- `templates/graph_context.cypher.mustache`
- `templates/graph_ingest.cypher.mustache`
- `templates/llm_answer_prompt.mustache`

Текущий пример домена: `app/domains/movies/`.

## Конфигурация

Основные файлы:
- `.env.example` — пример локальной конфигурации
- `.env` — локальная конфигурация
- `.env.docker` — override для контейнеров

Для контейнерного запуска `Ollama` ожидается на хост-машине, поэтому в `.env.docker` используется:
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- `LLM_BASE_URL=http://host.docker.internal:11434`

## Локальный запуск

1. Поднять инфраструктуру:

```bash
make infra-up
```

2. Запустить API:

```bash
make run
```

3. Загрузить данные домена:

```bash
make ingest-domain-data DOMAIN_NAME=movies
```

Если нужен явный датасет:

```bash
make ingest-domain-data DOMAIN_NAME=movies DATASET_FILE=app/domains/movies/example_data/kinopoisk-top250.jsonl
```

## HA-режим

Полный стек поднимается одной командой:

```bash
make ha-up
```

Что поднимается:
- `opensearch`
- `neo4j`
- `api-1`, `api-2`, `api-3`
- `api-lb`
- `prometheus`
- `grafana`
- `jaeger`
- `cadvisor`
- `locust`

После запуска `make ha-up` автоматически выполняется загрузка данных через `make ingest-domain-data`.

Остановка:

```bash
make ha-down
```

## Точки входа

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Debug UI: `http://localhost:8000/ui`
- Metrics: `http://localhost:8000/metrics`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- cAdvisor: `http://localhost:8088`
- Locust: `http://localhost:8089`

Grafana по умолчанию: `admin/admin`.

## API

Основные ручки:
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/documents`
- `POST /v1/documents/bulk`
- `POST /v1/search`
- `POST /v1/ask`

### Поиск

Пример запроса:

```json
{
  "query": "про космос",
  "limit": 10,
  "lexical_weight": 0.6,
  "vector_weight": 0.4
}
```

Особенности ответа:
- `payload.graph` содержит графовое расширение
- `debug` содержит lexical/vector score breakdown
- `debug.degraded_mode` показывает режим деградации:
  - `none`
  - `lexical_only_no_embedding`
  - `lexical_only_no_vector`
  - `no_graph_context`

### LLM-ответ

`POST /v1/ask` принимает вопрос и уже найденные `items`, затем возвращает:
- `answer` — итоговый текстовый ответ
- `think` — debug-поле, если модель вернула блок `<think>...</think>`
- `model` — имя активной модели

## Нагрузочное тестирование и наблюдаемость

Нагрузочный контур включен в `ha-up`.

Используются:
- `Locust` — сценарии нагрузки для `POST /v1/search` и `POST /v1/documents/bulk`
- `Prometheus` — сбор метрик API и контейнеров
- `Grafana` — готовый дашборд `GraphRAG Load Test Overview`
- `Jaeger` — distributed tracing
- `cAdvisor` — метрики CPU, RAM, сети по контейнерам

В Grafana можно:
- смотреть RPS и latency отдельно по `/v1/search`
- смотреть `p50`, `p90`, `p99`
- выбирать конкретный API instance или агрегированные метрики по всем инстансам
- анализировать CPU, RAM и network на уровне приложения и контейнеров

## Тесты

```bash
make test
```
