# Доменность в проекте: что нужно заполнить

Этот проект доменно-ориентирован через `DOMAIN_NAME` и `DOMAINS_ROOT`.
При старте сервис загружает артефакты из:

`<DOMAINS_ROOT>/<DOMAIN_NAME>/`

Например: `app/domains/movies/`.

## 1) Обязательная структура домена

Для нового домена должны существовать файлы:

- `<domain>/index_config.json`
- `<domain>/templates/lexical_search.mustache`
- `<domain>/templates/vector_search.mustache`
- `<domain>/templates/graph_context.cypher.mustache`
- `<domain>/templates/graph_ingest.cypher.mustache`
- `<domain>/templates/llm_answer_prompt.mustache`

Именно эти пути жестко загружает `DomainLoader`.

## 2) Что заполнять в `index_config.json`

## 2.1 `index`

Секция `index` целиком передается в OpenSearch при создании индекса.
Здесь вы задаете:

- `settings` (анализаторы, фильтры, knn и т.д.)
- `mappings.properties` (поля домена)

Важно: поле вектора можно не описывать вручную — сервис добавит/обновит его под `OPENSEARCH_VECTOR_FIELD` с размерностью `EMBEDDING_DIMENSION`.

## 2.2 `search.vector_source_fields`

Список полей документа, из которых собирается текст для эмбеддинга при индексации.

Пример:

```json
"vector_source_fields": ["overview", "title"]
```

Если список пуст, сервис возьмет все значения документа.

## 2.3 `search.graph`

Определяет доменную модель графа:

- `movie_label`
- `actor_label`
- `director_label`
- `screenwriter_label`
- `country_label`
- `acted_in_rel`
- `directed_rel`
- `wrote_rel`
- `produced_in_rel`

Эти значения подставляются в graph-шаблоны (`graph_context` и `graph_ingest`).

## 2.4 `search.graph.ingest`

Маппинг полей вашего JSON-документа в поля graph-ingest пайплайна:

- `title_field`
- `overview_field`
- `year_field`
- `rating_field`
- `rating_ball_field`
- `url_logo_field`
- `country_field`
- `director_field`
- `screenwriter_field`
- `actor_field`

Это нужно, чтобы `Neo4jAdapter.ingest_documents` корректно нормализовал данные перед `graph_ingest.cypher.mustache`.

## 2.5 `search.llm.domain_schema`

JSON-схема доменных данных для промпта LLM.
Используется в `LLMService` как часть `{{data_schema}}`.

## 3) Что заполнять в шаблонах

## 3.1 `lexical_search.mustache`

OpenSearch query template для лексического поиска.
В коде в него передаются параметры:

- `size`
- `query_text`
- `vector_field`

## 3.2 `vector_search.mustache`

OpenSearch query template для vector/knn поиска.
Параметры:

- `size`
- `query_vector`
- `vector_field`

## 3.3 `graph_context.cypher.mustache`

Cypher для обогащения поисковой выдачи графом.
Ожидаемые параметры исполнения:

- `item_ids`
- `person_limit`
- `related_limit`
- `shared_people_limit`

Ожидаемые поля в `RETURN` (для корректного парсинга адаптером):

- `item_id`
- `directors`
- `screenwriters`
- `actors`
- `countries`
- `related_movies`

## 3.4 `graph_ingest.cypher.mustache`

Cypher для записи документов в Neo4j при индексации.
На вход подается `rows`, где каждая строка после нормализации содержит:

- `id`, `title`, `overview`, `year`, `rating`, `rating_ball`, `url_logo`
- `countries`, `directors`, `screenwriters`, `actors`

## 3.5 `llm_answer_prompt.mustache`

Промпт для `/v1/ask`.
В шаблон подставляются:

- `{{question}}`
- `{{context}}`
- `{{data_schema}}`
- `{{allowed_ids}}`

## 4) Минимальный процесс добавления нового домена

1. Создать папку `app/domains/<new_domain>/`.
2. Добавить `index_config.json` с секциями `index` и `search`.
3. Добавить 5 шаблонов в `templates/`.
4. Положить тестовый JSONL в `example_data/` (опционально, для ingest).
5. Запустить сервис с `DOMAIN_NAME=<new_domain>`.

## 5) Что уже не нужно менять в коде

При корректно заполненных доменных артефактах не требуется править:

- `SearchService`
- `OpenSearchAdapter`
- `Neo4jAdapter`
- `LLMService`

Они работают через загруженные `DomainArtifacts`.
