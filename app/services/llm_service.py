"""LLM service for answer generation from search context."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed

from app.core.config import Settings
from app.core.domain_loader import DomainArtifacts
from app.core.logging import get_logger
from app.models.schemas import SearchItem

LLM_PROVIDER_OLLAMA = "ollama"
OLLAMA_RESPONSE_KEY = "response"
THINK_BLOCK_PATTERN = re.compile(
    r"<think>(.*?)</think>\s*", flags=re.DOTALL | re.IGNORECASE
)
JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", flags=re.DOTALL)
CONTEXT_CORE_FIELDS = (
    "movie",
    "year",
    "rating",
    "rating_ball",
    "country",
    "overview",
    "director",
    "screenwriter",
    "actors",
)


class LLMServiceError(Exception):
    """LLM service exception."""


class LLMService:
    """Generate answers with configured LLM provider."""

    def __init__(self, settings: Settings, domain_artifacts: DomainArtifacts) -> None:
        """Initialize service dependencies."""

        self._settings = settings
        self._domain_artifacts = domain_artifacts
        self._provider = settings.llm_provider.lower().strip()
        self._logger = get_logger(__name__)
        self._client = httpx.AsyncClient(
            base_url=self._settings.llm_base_url,
            timeout=self._settings.llm_timeout_seconds,
        )

    async def preload_model(self) -> None:
        """Warm up LLM model if enabled in config."""

        if not self._settings.llm_preload_on_startup:
            self._logger.info("llm_preload_skipped", reason="disabled_by_config")
            return

        if self._provider != LLM_PROVIDER_OLLAMA:
            self._logger.info(
                "llm_preload_skipped",
                reason="unsupported_provider",
                provider=self._provider,
            )
            return

        await self._call_ollama_generate(prompt="Скажи: ok")
        self._logger.info(
            "llm_model_loaded",
            provider=self._provider,
            model=self._settings.llm_model,
            base_url=self._settings.llm_base_url,
            endpoint=self._settings.llm_ollama_generate_endpoint,
        )

    async def close(self) -> None:
        """Close internal HTTP client."""

        await self._client.aclose()

    async def answer_from_items(
        self,
        question: str,
        items: list[SearchItem],
    ) -> dict[str, str | None]:
        """Generate answer from search items and question."""

        sorted_items = sorted(items, key=lambda item: item.score, reverse=True)
        context = self._build_context(items=sorted_items, limit=len(sorted_items))
        data_schema = self._build_data_schema(items=sorted_items)
        allowed_ids = [item.id for item in sorted_items]
        prompt = self._render_prompt(
            question=question,
            context=context,
            data_schema=data_schema,
            allowed_ids=allowed_ids,
        )

        if self._provider == LLM_PROVIDER_OLLAMA:
            raw_answer = await self._call_ollama_generate(prompt=prompt)
            return self._postprocess_answer(raw_answer=raw_answer)

        raise LLMServiceError(f"Unsupported llm provider: {self._provider}")

    def _build_context(self, items: list[SearchItem], limit: int) -> str:
        """Build JSON context block from top search items."""

        context_items: list[dict[str, Any]] = []
        for item in items[:limit]:
            payload = item.payload if isinstance(item.payload, dict) else {}
            core_payload = {
                key: payload.get(key) for key in CONTEXT_CORE_FIELDS if key in payload
            }
            graph_payload = payload.get("graph", {})
            context_items.append(
                {
                    "id": item.id,
                    "score": item.score,
                    "payload": core_payload,
                    "graph": self._compact_graph_context(graph_payload),
                }
            )
        return json.dumps(context_items, ensure_ascii=False, indent=2)

    def _compact_graph_context(self, graph_payload: Any) -> dict[str, Any]:
        """Compact graph context to reduce LLM noise."""

        if not isinstance(graph_payload, dict):
            return {}

        connections = graph_payload.get("connections", [])
        related_movies = graph_payload.get("related_movies", [])

        compact_connections: list[dict[str, str]] = []
        if isinstance(connections, list):
            for item in connections[:10]:
                if not isinstance(item, dict):
                    continue
                compact_connections.append(
                    {
                        "entity_type": str(item.get("entity_type", "")),
                        "entity": str(item.get("entity", "")),
                        "relation": str(item.get("relation", "")),
                    }
                )

        compact_related_movies: list[dict[str, Any]] = []
        if isinstance(related_movies, list):
            for item in related_movies[:5]:
                if not isinstance(item, dict):
                    continue
                compact_related_movies.append(
                    {
                        "id": str(item.get("id", "")),
                        "movie": str(item.get("movie", "")),
                        "shared_people_count": int(item.get("shared_people_count", 0)),
                    }
                )

        return {
            "connections": compact_connections,
            "related_movies": compact_related_movies,
        }

    def _build_data_schema(self, items: list[SearchItem]) -> str:
        """Build schema section for prompt using strict domain schema and observed keys."""

        payload_fields: set[str] = set()
        graph_connection_fields: set[str] = set()
        related_movie_fields: set[str] = set()

        for item in items:
            payload_fields.update(item.payload.keys())

            graph_payload = item.payload.get("graph", {})
            if isinstance(graph_payload, dict):
                connections = graph_payload.get("connections", [])
                if isinstance(connections, list):
                    for connection in connections:
                        if isinstance(connection, dict):
                            graph_connection_fields.update(connection.keys())

                related_movies = graph_payload.get("related_movies", [])
                if isinstance(related_movies, list):
                    for related_movie in related_movies:
                        if isinstance(related_movie, dict):
                            related_movie_fields.update(related_movie.keys())

        schema_payload = {
            "domain_schema": self._domain_artifacts.search_config.llm_domain_schema,
            "observed_in_request_items": {
                "search_item": {
                    "id": "str",
                    "score": "float",
                    "payload_fields": sorted(payload_fields),
                },
                "graph": {
                    "connections_fields": sorted(graph_connection_fields),
                    "related_movies_fields": sorted(related_movie_fields),
                },
            },
        }
        return json.dumps(schema_payload, ensure_ascii=False, indent=2)

    def _render_prompt(
        self, question: str, context: str, data_schema: str, allowed_ids: list[str]
    ) -> str:
        """Render domain prompt template."""

        template = self._domain_artifacts.templates.llm_answer_prompt
        return (
            template.replace("{{question}}", question)
            .replace("{{context}}", context)
            .replace("{{data_schema}}", data_schema)
            .replace("{{allowed_ids}}", ", ".join(allowed_ids))
        )

    def _postprocess_answer(self, raw_answer: str) -> dict[str, str | None]:
        """Normalize raw LLM response and split think/debug from answer."""

        think = self._extract_think(raw_answer=raw_answer)
        cleaned = THINK_BLOCK_PATTERN.sub("", raw_answer).strip()
        if not cleaned:
            return {"answer": "Недостаточно данных в контексте.", "think": think}

        parsed = self._try_extract_answer_json(cleaned)
        if parsed is None:
            return {"answer": cleaned, "think": think}

        answer_text = str(parsed.get("answer", "")).strip()
        if not answer_text:
            return {"answer": cleaned, "think": think}
        return {"answer": answer_text, "think": think}

    def _extract_think(self, raw_answer: str) -> str | None:
        """Extract think text from model response for debugging."""

        matches = THINK_BLOCK_PATTERN.findall(raw_answer)
        if not matches:
            return None
        parts = [item.strip() for item in matches if item.strip()]
        if not parts:
            return None
        return "\n\n".join(parts)

    def _try_extract_answer_json(self, text: str) -> dict[str, Any] | None:
        """Try to parse JSON object from model output."""

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass

        match = JSON_BLOCK_PATTERN.search(text)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            return None
        return None

    async def _call_ollama_generate(self, prompt: str) -> str:
        """Call Ollama generate endpoint and return plain answer text."""

        payload = {
            "model": self._settings.llm_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self._settings.llm_temperature},
        }
        body = await self._request_with_retry(
            path=self._settings.llm_ollama_generate_endpoint, payload=payload
        )
        answer = str(body.get(OLLAMA_RESPONSE_KEY, "")).strip()
        if not answer:
            raise LLMServiceError("LLM response is empty")
        return answer

    async def _request_with_retry(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute LLM request with retry policy."""

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._settings.retry_attempts),
            wait=wait_fixed(self._settings.retry_wait_seconds),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self._client.post(path, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict):
                        raise LLMServiceError("LLM response must be a JSON object")
                    return body
                except httpx.HTTPStatusError as error:
                    status_code = error.response.status_code
                    body_preview = error.response.text[:500]
                    raise LLMServiceError(
                        f"LLM HTTP status error ({status_code}) on {path}: {body_preview}"
                    ) from error
                except httpx.TimeoutException as error:
                    raise LLMServiceError(
                        f"LLM timeout on {path} after {self._settings.llm_timeout_seconds}s "
                        f"(model={self._settings.llm_model})"
                    ) from error
                except httpx.HTTPError as error:
                    raise LLMServiceError(
                        f"LLM transport error on {path}: {type(error).__name__}: {error!r}"
                    ) from error
                except ValueError as error:
                    raise LLMServiceError(
                        f"LLM returned invalid JSON: {error}"
                    ) from error

        raise LLMServiceError("LLM request failed after retries")
