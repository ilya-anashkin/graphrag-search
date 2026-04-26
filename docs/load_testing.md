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
  - RPS по `/v1/search`;
  - latency quantiles (`p99`, `p95`, `p50`) по `/v1/search`;
  - in-progress requests, error rate как доля `4xx`/`5xx` от общего RPS;
  - системные графики приложения: CPU, RAM, HTTP ingress/egress bytes;
  - системные графики контейнеров: CPU, RAM, Network (через `cAdvisor`);
  - переменная `Metrics Window` для единого окна агрегации по всем графикам.
  - переменная `API Instance`:
    - `All` — агрегированно по всем API-инстансам;
    - конкретный `instance` — метрики отдельного API.

4. Генерация нагрузки (`Locust`):
- сценарии в `loadtest/locustfile.py`:
  - `POST /v1/search`
  - профили нагрузки:
    - `step` — ступенчатый рост
    - `spike` — резкий пик и спад
    - `soak` — длительная равномерная нагрузка

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

Для shape-сценариев основным источником профиля является env-параметр `LOCUST_LOAD_SCENARIO`.
Ручные значения `Number of users` и `Spawn rate` в UI при активном shape-классе Locust не являются главным управляющим сигналом.

Старт теста и наблюдение за метриками в Grafana.

## Параметры нагрузки

Для сервиса `locust` в `docker-compose.ha.yml` доступны:

- `LOCUST_LOAD_SCENARIO` — `step`, `spike`, `soak`;
- `LOCUST_SEARCH_MODE` — `lexical`, `lexical_vector`, `lexical_vector_graph`;
- `LOCUST_SEARCH_LIMIT` — `limit` для поисковых запросов;
- `LOCUST_SEARCH_TASK_WEIGHT` — вес поисковой task внутри user-profile.

## Набор поисковых запросов

В `Locust` используются фиксированные запросы для функционально близкой нагрузки:

- `про робота в космосе`
- `про магию и волшебников`
- `с Харрисоном Фордом`
- `Кристофера Нолана`
- `про космос с Харрисоном Фордом`
- `похожие на Интерстеллар по создателям`
- `Похожие по актёрам Пятого Элемента`
- `Похожие по сценарию Валли`
- `что посмотреть после Темного рыцаря`
- `какие фильмы похожи на ВАЛЛ·И`
- `какие актеры снимались в фильмах про космос`
- `какие режиссеры есть среди фильмов про магию`
- `какие страны встречаются среди мультфильмов`
- `про космос с Леонардо ДиКаприо`
- `российские фильмы Кристофера Нолана`
- `про Бэтмена с Джимом Керри`

## Остановка

```bash
make ha-down
```
