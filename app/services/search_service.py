"""Application search service."""

from typing import Any

from app.adapters.neo4j_client import Neo4jAdapter
from app.adapters.opensearch_client import OpenSearchAdapter
from app.core.config import Settings
from app.core.domain_loader import DomainArtifacts
from app.core.logging import get_logger
from app.models.schemas import IndexDocumentRequest, SearchItem
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError

CHANNEL_LEXICAL = "lexical"
CHANNEL_VECTOR = "vector"
NORMALIZED_SCORE_KEY = "normalized_score"
DEFAULT_SCORE = 0.0


class SearchService:
    """Coordinates indexing and hybrid search flows."""

    def __init__(
        self,
        opensearch_adapter: OpenSearchAdapter,
        neo4j_adapter: Neo4jAdapter,
        embedding_service: EmbeddingService,
        settings: Settings,
        domain_artifacts: DomainArtifacts,
    ) -> None:
        """Initialize service dependencies."""

        self._opensearch_adapter = opensearch_adapter
        self._neo4j_adapter = neo4j_adapter
        self._embedding_service = embedding_service
        self._settings = settings
        self._domain_artifacts = domain_artifacts
        self._logger = get_logger(__name__)

    async def index_document(self, payload: IndexDocumentRequest) -> bool:
        """Index a document and persist generated embedding vector."""

        embedding_text = self._build_embedding_text(document=payload.document)
        try:
            embedding = await self._embedding_service.embed_text(embedding_text)
        except (EmbeddingServiceError, ValueError) as error:
            self._logger.error("embedding_build_failed", error=str(error), document_id=payload.id)
            return False

        return await self._opensearch_adapter.index_document(
            document_id=payload.id,
            document=payload.document,
            embedding=embedding,
        )

    async def index_documents_bulk(
        self,
        payloads: list[IndexDocumentRequest],
        batch_size: int | None = None,
    ) -> tuple[int, list[str]]:
        """Index multiple documents in batches and return indexed count and failed ids."""

        if not payloads:
            return 0, []

        resolved_batch_size = batch_size or self._settings.bulk_index_batch_size
        indexed_count = 0
        failed_ids: list[str] = []

        for chunk in self._chunk_payloads(payloads=payloads, batch_size=resolved_batch_size):
            prepared_items: list[tuple[str, dict[str, Any], list[float]]] = []
            for item in chunk:
                embedding_text = self._build_embedding_text(document=item.document)
                try:
                    embedding = await self._embedding_service.embed_text(embedding_text)
                except (EmbeddingServiceError, ValueError) as error:
                    self._logger.error("embedding_build_failed", error=str(error), document_id=item.id)
                    failed_ids.append(item.id)
                    continue
                prepared_items.append((item.id, item.document, embedding))

            if not prepared_items:
                continue

            succeeded_ids, chunk_failed_ids = await self._opensearch_adapter.bulk_index_documents(prepared_items)
            indexed_count += len(succeeded_ids)
            failed_ids.extend(chunk_failed_ids)

        return indexed_count, failed_ids

    def _chunk_payloads(
        self,
        payloads: list[IndexDocumentRequest],
        batch_size: int,
    ) -> list[list[IndexDocumentRequest]]:
        """Split payloads into fixed-size chunks."""

        return [payloads[index : index + batch_size] for index in range(0, len(payloads), batch_size)]

    def _build_embedding_text(self, document: dict[str, Any]) -> str:
        """Build embedding source text from configured domain fields."""

        fields = self._domain_artifacts.search_config.vector_source_fields
        if not fields:
            return "\n".join(str(value) for value in document.values() if value is not None)

        parts = [str(document.get(field, "")) for field in fields if document.get(field) not in (None, "")]
        return "\n".join(parts)

    async def search(
        self,
        query: str,
        limit: int,
        lexical_weight: float | None = None,
        vector_weight: float | None = None,
    ) -> list[SearchItem]:
        """Run lexical and vector searches and return weighted merged results."""

        resolved_lexical_weight, resolved_vector_weight = self._resolve_weights(
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )
        try:
            query_embedding = await self._embedding_service.embed_text(query)
        except (EmbeddingServiceError, ValueError) as error:
            self._logger.error("embedding_build_failed", error=str(error))
            return []

        lexical_limit = max(limit, self._settings.lexical_candidate_size)
        vector_limit = max(limit, self._settings.vector_candidate_size)

        lexical_results = await self._opensearch_adapter.lexical_search(query=query, limit=lexical_limit)
        vector_results = await self._opensearch_adapter.vector_search(
            query_vector=query_embedding,
            limit=vector_limit,
        )

        lexical_results = self._normalize_channel_scores(results=lexical_results)
        vector_results = self._normalize_channel_scores(results=vector_results)

        weighted_items = self._merge_weighted_results(
            lexical_results=lexical_results,
            vector_results=vector_results,
            lexical_weight=resolved_lexical_weight,
            vector_weight=resolved_vector_weight,
        )

        sorted_items = sorted(weighted_items.values(), key=lambda item: item.score, reverse=True)
        return sorted_items[:limit]

    def _resolve_weights(self, lexical_weight: float | None, vector_weight: float | None) -> tuple[float, float]:
        """Resolve effective weights and normalize them to sum 1."""

        resolved_lexical_weight = (
            self._settings.lexical_search_weight if lexical_weight is None else lexical_weight
        )
        resolved_vector_weight = self._settings.vector_search_weight if vector_weight is None else vector_weight

        total_weight = resolved_lexical_weight + resolved_vector_weight
        if total_weight <= 0:
            return self._settings.lexical_search_weight, self._settings.vector_search_weight
        return resolved_lexical_weight / total_weight, resolved_vector_weight / total_weight

    def _normalize_channel_scores(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize channel scores with min-max scaling to [0, 1]."""

        if not results:
            return results

        scores = [float(item.get("score", DEFAULT_SCORE)) for item in results]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        normalized_results: list[dict[str, Any]] = []
        for item in results:
            raw_score = float(item.get("score", DEFAULT_SCORE))
            if score_range == 0.0:
                normalized_score = 1.0 if raw_score > 0.0 else 0.0
            else:
                normalized_score = (raw_score - min_score) / score_range

            updated_item = dict(item)
            updated_item[NORMALIZED_SCORE_KEY] = normalized_score
            normalized_results.append(updated_item)

        return normalized_results

    def _merge_weighted_results(
        self,
        lexical_results: list[dict[str, Any]],
        vector_results: list[dict[str, Any]],
        lexical_weight: float,
        vector_weight: float,
    ) -> dict[str, SearchItem]:
        """Merge lexical and vector result lists into weighted scores."""

        merged: dict[str, SearchItem] = {}

        self._accumulate_results(
            merged=merged,
            results=lexical_results,
            weight=lexical_weight,
            channel=CHANNEL_LEXICAL,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )
        self._accumulate_results(
            merged=merged,
            results=vector_results,
            weight=vector_weight,
            channel=CHANNEL_VECTOR,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )

        return merged

    def _build_debug_payload(self, lexical_weight: float, vector_weight: float) -> dict[str, Any]:
        """Build initial per-channel debug payload."""

        return {
            CHANNEL_LEXICAL: {
                "raw_score": 0.0,
                "normalized_score": 0.0,
                "weight": lexical_weight,
                "weighted_score": 0.0,
            },
            CHANNEL_VECTOR: {
                "raw_score": 0.0,
                "normalized_score": 0.0,
                "weight": vector_weight,
                "weighted_score": 0.0,
            },
            "combined_score": 0.0,
        }

    def _accumulate_results(
        self,
        merged: dict[str, SearchItem],
        results: list[dict[str, Any]],
        weight: float,
        channel: str,
        lexical_weight: float,
        vector_weight: float,
    ) -> None:
        """Accumulate weighted score from one search channel into merged dictionary."""

        for result in results:
            result_id = str(result.get("id", ""))
            if not result_id:
                continue

            raw_score = float(result.get("score", DEFAULT_SCORE))
            normalized_score = float(result.get(NORMALIZED_SCORE_KEY, DEFAULT_SCORE))
            weighted_score = normalized_score * weight
            existing_item = merged.get(result_id)
            if existing_item is None:
                debug_payload = self._build_debug_payload(
                    lexical_weight=lexical_weight,
                    vector_weight=vector_weight,
                )
                merged[result_id] = SearchItem(
                    source=str(result.get("source", "opensearch")),
                    id=result_id,
                    score=0.0,
                    payload=result.get("payload", {}),
                    debug=debug_payload,
                )
                existing_item = merged[result_id]

            channel_debug = existing_item.debug.get(channel, {})
            channel_debug["raw_score"] = float(channel_debug.get("raw_score", 0.0)) + raw_score
            channel_debug["normalized_score"] = (
                float(channel_debug.get("normalized_score", 0.0)) + normalized_score
            )
            channel_debug["weight"] = weight
            channel_debug["weighted_score"] = float(channel_debug.get("weighted_score", 0.0)) + weighted_score
            existing_item.debug[channel] = channel_debug
            existing_item.score += weighted_score
            existing_item.debug["combined_score"] = existing_item.score

    async def check_dependencies(self) -> bool:
        """Return True when all service dependencies are healthy."""

        opensearch_ok = await self._opensearch_adapter.check_health()
        neo4j_ok = await self._neo4j_adapter.check_health()
        return opensearch_ok and neo4j_ok
