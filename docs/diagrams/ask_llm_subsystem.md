# Подсистема /v1/ask (LLM-ответ по результатам поиска)

Диаграмма: `docs/diagrams/ask_llm_subsystem.puml`

## Что отражено

1. Вход в подсистему:
`POST /v1/ask` с `question` и `items`.

2. Валидация на уровне API:
- если `items` пустой, возвращается `422`.

3. Логика в `LLMService.answer_from_items`:
- сортировка `items` по score (по убыванию);
- построение `context` (core payload + компактный graph);
- построение `data_schema` (domain schema + наблюдаемые поля);
- рендер prompt из доменного шаблона;
- вызов Ollama `/api/generate`;
- постобработка результата:
  - извлечение `<think>...</think>` в поле `think`;
  - очистка answer от think-блока;
  - попытка взять `answer` из JSON-ответа;
  - fallback на обычный текст.

4. Формирование HTTP-ответа:
API добавляет:
- `model` через `SearchService.get_llm_model()`;
- `used_items` через `SearchService.resolve_used_context_items(...)`.

5. Ошибка LLM:
- при `LLMServiceError` API возвращает `502 Bad Gateway`.

## Ограничение диаграммы

Диаграмма отражает только текущий реализованный поток `/v1/ask` в коде проекта, без внешних или гипотетических шагов.
