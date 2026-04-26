# graphrag-search

English version: `README.en.md`

Гибридная поисковая система на `FastAPI` с `OpenSearch`, `Neo4j` и `Ollama`.

Что есть в проекте:
- гибридный поиск: `lexical`, `lexical_vector`, `lexical_vector_graph`
- графовое обогащение выдачи через `Neo4j`
- LLM-ответ по найденным документам
- debug UI в браузере
- HA и контур нагрузочного тестирования

## Стек

- `FastAPI`
- `OpenSearch`
- `Neo4j`
- `Ollama`
- `Prometheus`
- `Grafana`
- `Jaeger`
- `Locust`

## Конфигурация

Основные файлы:
- `.env.example` — пример конфигурации
- `.env` — локальные настройки
- `.env.docker` — override для контейнеров

Текущий домен по умолчанию: `movies`.

## Локальный запуск

1. Поднять инфраструктуру:

```bash
make infra-up
```

2. Запустить API:

```bash
make run
```

3. Загрузить данные:

```bash
make ingest-domain-data DOMAIN_NAME=movies
```

Если нужен увеличенный датасет:

```bash
make ingest-domain-data-expanded DOMAIN_NAME=movies DATASET_MULTIPLIER=10
```

## HA и нагрузочное тестирование

Поднять полный стек:

```bash
make ha-up
```

Остановить:

```bash
make ha-down
```

Сервисы:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- UI: `http://localhost:8000/ui`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- Locust: `http://localhost:8089`

## Основные API

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/documents`
- `POST /v1/documents/bulk`
- `POST /v1/search`
- `POST /v1/ask`

Пример поиска:

```json
{
  "query": "про космос",
  "limit": 10,
  "search_mode": "lexical_vector_graph",
  "lexical_weight": 0.6,
  "vector_weight": 0.4
}
```

Поддерживаемые `search_mode`:
- `lexical`
- `lexical_vector`
- `lexical_vector_graph`

## Доменная структура

Для домена используются файлы в `app/domains/<domain_name>/`:
- `index_config.json`
- `templates/lexical_search.mustache`
- `templates/vector_search.mustache`
- `templates/graph_context.cypher.mustache`
- `templates/graph_ingest.cypher.mustache`
- `templates/llm_answer_prompt.mustache`

## Тесты

```bash
make test
```
