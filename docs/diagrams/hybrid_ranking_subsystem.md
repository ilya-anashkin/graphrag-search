# Гибридное ранжирование в системе

Диаграмма: `docs/diagrams/hybrid_ranking_subsystem.puml`

## Как работает гибридное ранжирование

1. Вход: `POST /v1/search`
- Принимаются `query`, `limit`, опционально `lexical_weight`, `vector_weight`.

2. Разрешение весов каналов
- Если веса не переданы, используются значения из конфигурации.
- Если сумма весов `<= 0`, используется fallback на конфигурационные веса.
- Иначе веса нормализуются, чтобы сумма была равна 1.

3. Подготовка кандидатов
- Строится embedding для `query`.
- Определяются размеры пулов кандидатов:
  - `lexical_limit = max(limit, LEXICAL_CANDIDATE_SIZE)`
  - `vector_limit = max(limit, VECTOR_CANDIDATE_SIZE)`
- Выполняются два поиска в OpenSearch: lexical и vector.

4. Нормализация score по каналам
- Для каждого канала используется min-max нормализация.
- Спец-случай `range=0`:
  - при `raw_score > 0` -> `normalized_score = 1`
  - при `raw_score = 0` -> `normalized_score = 0`

5. Merge и вычисление итогового score
- Для каждого документа считается:
  - `lexical_weighted = lexical_normalized * lexical_weight`
  - `vector_weighted = vector_normalized * vector_weight`
  - `combined_score = lexical_weighted + vector_weighted`
- В `debug` сохраняются raw/normalized/weight/weighted по каждому каналу.

6. Пост-фильтрация
- Если `vector_weight > 0`, удаляются документы вида:
  - `lexical_raw > 0` и `vector_raw = 0`
- Это убирает «чисто лексические» попадания при включенном векторном канале.

7. Финальный ранжированный список
- Сортировка по `combined_score` по убыванию.
- Ограничение до `limit`.
- Далее результат передается на следующий этап (например, графовое обогащение).

## Ограничение диаграммы

Диаграмма описывает именно механику гибридного ранжирования в текущем `SearchService` без добавления несуществующих алгоритмов.
