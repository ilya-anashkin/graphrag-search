# Подсистема выполнения запросов

Диаграмма: `docs/diagrams/query_execution_subsystem.puml`

## Что отражено

1. Вход в подсистему:
`POST /v1/search` с полями `query`, `limit`, опционально `lexical_weight` и `vector_weight`.

2. Основной pipeline в `SearchService.search`:
- нормализация весов каналов (`resolve_weights`);
- запуск lexical-канала в OpenSearch (`lexical_search`);
- попытка запуска vector-канала:
  - построение embedding для query;
  - `vector_search` в OpenSearch;
  - при сбое embedding или пустом/неуспешном vector-канале сервис деградирует в lexical-only режим;
- min-max нормализация score в каждом канале;
- merge результатов с учетом весов;
- установка `debug.degraded_mode`:
  - `none`;
  - `lexical_only_no_embedding`;
  - `lexical_only_no_vector`;
- сортировка по combined score и ограничение `limit`.

3. Графовое обогащение результатов:
- всегда выполняется `fetch_graph_context` в Neo4j;
- найденный контекст добавляется в `payload.graph` соответствующих элементов.

4. Выход:
`SearchResponse(items=[...])`.

## Важные ветки

- Если embedding query не построен, сервис не падает в пустой ответ: выполняется lexical-only поиск.
- Если vector-поиск неуспешен/пустой, сервис также возвращает lexical-only результаты.
- Если запрос в Neo4j неуспешен, адаптер возвращает пустой контекст, а сервис возвращает результаты без `payload.graph` для таких элементов и проставляет `debug.degraded_mode = no_graph_context`.

## Ограничение диаграммы

Диаграмма показывает только реализованный в коде runtime-поток подсистемы поиска. В ней нет логики, отсутствующей в проекте.
