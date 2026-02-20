"""HTTP adapter for OpenSearch."""

import json
from copy import deepcopy
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed

from app.core.config import Settings
from app.core.domain_loader import DomainArtifacts
from app.core.logging import get_logger

OPEN_SEARCH_HITS_KEY = "hits"
OPEN_SEARCH_SOURCE_KEY = "_source"
OPEN_SEARCH_ID_KEY = "_id"
OPEN_SEARCH_SCORE_KEY = "_score"
OPEN_SEARCH_REASON_KEY = "reason"
OPEN_SEARCH_ERROR_KEY = "error"
OPEN_SEARCH_STATUS_CREATED = 201
OPEN_SEARCH_STATUS_OK = 200
OPEN_SEARCH_STATUS_RESOURCE_EXISTS = 400
OPEN_SEARCH_INDEX_PATH_TEMPLATE = "/{index}"
OPEN_SEARCH_DOCUMENT_PATH_TEMPLATE = "/{index}/_doc/{document_id}?refresh=true"
OPEN_SEARCH_BULK_PATH = "/_bulk?refresh=true"
OPEN_SEARCH_SEARCH_TEMPLATE_PATH_TEMPLATE = "/{index}/_search/template"
OPEN_SEARCH_HEALTH_PATH = "/_cluster/health"
VECTOR_TYPE = "knn_vector"
DIMENSION_KEY = "dimension"
PROPERTIES_KEY = "properties"
MAPPINGS_KEY = "mappings"


class OpenSearchAdapter:
    """OpenSearch adapter with retry, timeout and error handling."""

    def __init__(self, settings: Settings, domain_artifacts: DomainArtifacts) -> None:
        """Initialize adapter with settings and HTTP client."""

        self._settings = settings
        self._domain_artifacts = domain_artifacts
        self._logger = get_logger(__name__)
        self._client = httpx.AsyncClient(
            base_url=settings.opensearch_base_url,
            timeout=settings.api_timeout_seconds,
        )

    async def close(self) -> None:
        """Close underlying HTTP client."""

        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        allow_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with retries and return JSON body."""

        allowed_statuses = allow_statuses or {OPEN_SEARCH_STATUS_OK}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._settings.retry_attempts),
            wait=wait_fixed(self._settings.retry_wait_seconds),
            reraise=True,
        ):
            with attempt:
                response = await self._client.request(method=method, url=path, json=json_data)
                if response.status_code not in allowed_statuses:
                    response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
        return {}

    async def _request_ndjson(self, path: str, payload: str) -> dict[str, Any]:
        """Execute NDJSON request with retries and return JSON body."""

        headers = {"Content-Type": "application/x-ndjson"}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._settings.retry_attempts),
            wait=wait_fixed(self._settings.retry_wait_seconds),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(path, content=payload.encode("utf-8"), headers=headers)
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
        return {}

    async def ensure_index(self) -> bool:
        """Ensure target index exists with loaded domain mapping."""

        index_path = OPEN_SEARCH_INDEX_PATH_TEMPLATE.format(index=self._settings.opensearch_index)
        index_body = self._build_index_body()

        try:
            payload = await self._request(
                method="PUT",
                path=index_path,
                json_data=index_body,
                allow_statuses={
                    OPEN_SEARCH_STATUS_OK,
                    OPEN_SEARCH_STATUS_CREATED,
                    OPEN_SEARCH_STATUS_RESOURCE_EXISTS,
                },
            )
            error_data = payload.get(OPEN_SEARCH_ERROR_KEY, {})
            reason = str(error_data.get(OPEN_SEARCH_REASON_KEY, ""))
            return "already exists" in reason or not error_data
        except httpx.HTTPError as error:
            self._logger.error("opensearch_ensure_index_failed", error=str(error))
            return False

    def _build_index_body(self) -> dict[str, Any]:
        """Build index body and enforce configured embedding dimension."""

        index_body = deepcopy(self._domain_artifacts.index_body)
        properties = index_body.get(MAPPINGS_KEY, {}).get(PROPERTIES_KEY, {})

        vector_field = self._settings.opensearch_vector_field
        if vector_field not in properties:
            properties[vector_field] = {"type": VECTOR_TYPE, DIMENSION_KEY: self._settings.embedding_dimension}
        elif properties[vector_field].get("type") == VECTOR_TYPE:
            properties[vector_field][DIMENSION_KEY] = self._settings.embedding_dimension

        index_body.setdefault(MAPPINGS_KEY, {})[PROPERTIES_KEY] = properties
        return index_body

    async def index_document(
        self,
        document_id: str,
        document: dict[str, Any],
        embedding: list[float],
    ) -> bool:
        """Index a domain document with precomputed embedding vector."""

        if not await self.ensure_index():
            return False

        document_path = OPEN_SEARCH_DOCUMENT_PATH_TEMPLATE.format(
            index=self._settings.opensearch_index,
            document_id=document_id,
        )
        payload = dict(document)
        payload[self._settings.opensearch_vector_field] = embedding

        try:
            await self._request(
                method="PUT",
                path=document_path,
                json_data=payload,
                allow_statuses={OPEN_SEARCH_STATUS_OK, OPEN_SEARCH_STATUS_CREATED},
            )
            return True
        except httpx.HTTPError as error:
            self._logger.error("opensearch_index_document_failed", error=str(error), document_id=document_id)
            return False

    async def bulk_index_documents(
        self,
        items: list[tuple[str, dict[str, Any], list[float]]],
    ) -> tuple[list[str], list[str]]:
        """Bulk index documents and return succeeded and failed ids."""

        if not items:
            return [], []
        if not await self.ensure_index():
            return [], [item[0] for item in items]

        ndjson_lines: list[str] = []
        for document_id, document, embedding in items:
            action = {"index": {"_index": self._settings.opensearch_index, "_id": document_id}}
            source = dict(document)
            source[self._settings.opensearch_vector_field] = embedding
            ndjson_lines.append(json.dumps(action, ensure_ascii=False))
            ndjson_lines.append(json.dumps(source, ensure_ascii=False))
        payload = "\n".join(ndjson_lines) + "\n"

        try:
            response_payload = await self._request_ndjson(path=OPEN_SEARCH_BULK_PATH, payload=payload)
        except httpx.HTTPError as error:
            self._logger.error("opensearch_bulk_index_failed", error=str(error))
            return [], [item[0] for item in items]

        succeeded_ids: list[str] = []
        failed_ids: list[str] = []
        response_items = response_payload.get("items", [])
        for item in response_items:
            index_result = item.get("index", {})
            document_id = str(index_result.get("_id", ""))
            status_code = int(index_result.get("status", 500))
            if 200 <= status_code < 300:
                succeeded_ids.append(document_id)
            else:
                failed_ids.append(document_id)

        return succeeded_ids, failed_ids

    async def lexical_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Run lexical search using loaded mustache template."""

        search_path = OPEN_SEARCH_SEARCH_TEMPLATE_PATH_TEMPLATE.format(index=self._settings.opensearch_index)
        params = {
            "size": limit,
            "query_text": query,
            "vector_field": self._settings.opensearch_vector_field,
        }
        return await self._search_template(
            path=search_path,
            template=self._domain_artifacts.templates.lexical_search,
            params=params,
            search_type="lexical",
        )

    async def vector_search(self, query_vector: list[float], limit: int) -> list[dict[str, Any]]:
        """Run vector similarity search using loaded mustache template."""

        search_path = OPEN_SEARCH_SEARCH_TEMPLATE_PATH_TEMPLATE.format(index=self._settings.opensearch_index)
        params = {
            "size": limit,
            "query_vector": query_vector,
            "vector_field": self._settings.opensearch_vector_field,
        }
        return await self._search_template(
            path=search_path,
            template=self._domain_artifacts.templates.vector_search,
            params=params,
            search_type="vector",
        )

    async def _search_template(
        self,
        path: str,
        template: str,
        params: dict[str, Any],
        search_type: str,
    ) -> list[dict[str, Any]]:
        """Execute OpenSearch mustache template search and map hits."""

        body = {
            "source": template,
            "params": params,
        }

        try:
            payload = await self._request(method="POST", path=path, json_data=body)
            hits = payload.get(OPEN_SEARCH_HITS_KEY, {}).get(OPEN_SEARCH_HITS_KEY, [])
            return [
                {
                    "source": "opensearch",
                    "id": str(item.get(OPEN_SEARCH_ID_KEY, "")),
                    "score": float(item.get(OPEN_SEARCH_SCORE_KEY, 0.0)),
                    "payload": item.get(OPEN_SEARCH_SOURCE_KEY, {}),
                    "search_type": search_type,
                }
                for item in hits
            ]
        except (httpx.HTTPError, ValueError) as error:
            self._logger.error("opensearch_search_failed", error=str(error), search_type=search_type)
            return []

    async def check_health(self) -> bool:
        """Return True when OpenSearch health endpoint is reachable."""

        try:
            await self._request(method="GET", path=OPEN_SEARCH_HEALTH_PATH)
            return True
        except httpx.HTTPError as error:
            self._logger.error("opensearch_health_failed", error=str(error))
            return False
