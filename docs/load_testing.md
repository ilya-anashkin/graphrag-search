# Нагрузочное тестирование

## Что реализовано

1. Метрики приложения (`Prometheus`):
- endpoint `GET /metrics` в FastAPI;
- метрики:
  - `graphrag_http_requests_total{method,path,status}`
  - `graphrag_http_request_duration_seconds{method,path}`
  - `graphrag_http_requests_in_progress{method,path}`
  - `graphrag_http_request_size_bytes_total{method,path}`
  - `graphrag_http_response_size_bytes_total{method,path,status}`

2. Трейсинг (`OpenTelemetry` + `Jaeger`):
- трейсинг входящих запросов FastAPI;
- трейсинг исходящих HTTP-вызовов (`httpx`) к OpenSearch/Ollama;
- экспорт спанов в Jaeger через OTLP (`TRACING_OTLP_ENDPOINT`).

3. Визуализация (`Grafana`):
- автопровиженинг data source и дашборда;
- дашборд: `GraphRAG Load Test Overview`:
  - RPS по `/v1/search` и `/v1/documents/bulk`;
  - latency quantiles (`p99`, `p90`, `p50`) по этим ручкам;
  - in-progress requests, error rate;
  - системные графики приложения: CPU, RAM, HTTP ingress/egress bytes;
  - системные графики контейнеров: CPU, RAM, Network (через `cAdvisor`).
  - переменная `API Instance`:
    - `All` — агрегированно по всем API-инстансам;
    - конкретный `instance` — метрики отдельного API.

4. Генерация нагрузки (`Locust`):
- сценарии в `loadtest/locustfile.py`:
  - `POST /v1/search`
  - `POST /v1/documents/bulk` (документы из JSONL домена фильмов)

## Быстрый запуск

1. Поднять HA-стек вместе с контуром нагрузочного тестирования:

```bash
make ha-up
```

2. Открыть сервисы:

- Locust: `http://localhost:8089`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (`admin/admin`)
- cAdvisor: `http://localhost:8088`
- Jaeger: `http://localhost:16686`
- Метрики API: `http://localhost:8000/metrics`

## Как запускать тест

В Locust UI:

- `Number of users`: например, `100`
- `Spawn rate`: например, `10`
- `Host`: `http://api-lb` (по умолчанию уже задан в сервисе Locust)

Старт теста и наблюдение за метриками в Grafana.

## Параметры bulk-нагрузки

Для сервиса `locust` в `docker-compose.ha.yml` доступны:

- `LOCUST_BULK_DATASET_FILE` — путь к JSONL внутри контейнера;
- `LOCUST_BULK_BATCH_SIZE` — размер батча в запросе `/v1/documents/bulk`;
- `LOCUST_BULK_SAMPLES_LIMIT` — сколько документов считывать из файла в кэш Locust.

## Остановка

```bash
make ha-down
```
