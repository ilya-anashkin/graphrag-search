"""Search service tests."""

from app.core.config import Settings
from app.core.domain_loader import DomainArtifacts, DomainSearchConfig, DomainTemplates
from app.models.schemas import IndexDocumentRequest, SearchItem
from app.services.search_service import SearchService


class FakeOpenSearchAdapter:
    """Fake OpenSearch adapter."""

    async def lexical_search(self, query: str, limit: int) -> list[dict[str, object]]:
        """Return fake lexical data."""

        return [
            {
                "source": "opensearch",
                "id": "doc-1",
                "score": 2.0,
                "payload": {"title": query},
                "search_type": "lexical",
            }
        ]

    async def vector_search(self, query_vector: list[float], limit: int) -> list[dict[str, object]]:
        """Return fake vector data."""

        return [
            {
                "source": "opensearch",
                "id": "doc-1",
                "score": 1.0,
                "payload": {"title": "vector"},
                "search_type": "vector",
            },
            {
                "source": "opensearch",
                "id": "doc-2",
                "score": 1.5,
                "payload": {"title": "vector-2"},
                "search_type": "vector",
            },
        ]

    async def index_document(
        self,
        document_id: str,
        document: dict[str, object],
        embedding: list[float],
    ) -> bool:
        """Accept indexed document."""

        return bool(document_id and document and embedding)

    async def check_health(self) -> bool:
        """Return fake healthy state."""

        return True

    async def bulk_index_documents(
        self,
        items: list[tuple[str, dict[str, object], list[float]]],
    ) -> tuple[list[str], list[str]]:
        """Accept bulk indexed documents."""

        succeeded_ids = [item[0] for item in items]
        return succeeded_ids, []


class FakeNeo4jAdapter:
    """Fake Neo4j adapter."""

    async def check_health(self) -> bool:
        """Return fake healthy state."""

        return True


class FakeEmbeddingService:
    """Fake embedding service."""

    async def embed_text(self, text: str) -> list[float]:
        """Return deterministic fake embedding."""

        return [0.1, 0.2, 0.3]

    async def close(self) -> None:
        """No-op close for interface compatibility."""

        return None


def build_domain_artifacts() -> DomainArtifacts:
    """Build fake domain artifacts."""

    return DomainArtifacts(
        domain_name="movies",
        index_body={"settings": {}, "mappings": {"properties": {}}},
        search_config=DomainSearchConfig(vector_source_fields=["movie", "overview"]),
        templates=DomainTemplates(lexical_search="{}", vector_search="{}"),
    )


async def test_service_hybrid_merge_with_weights() -> None:
    """Service should merge lexical and vector channels by weights."""

    settings = Settings(LEXICAL_SEARCH_WEIGHT=0.7, VECTOR_SEARCH_WEIGHT=0.3)
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )

    result = await service.search(query="abc", limit=10)

    assert all(isinstance(item, SearchItem) for item in result)
    assert [item.id for item in result] == ["doc-1", "doc-2"]
    assert result[0].score > result[1].score
    assert result[0].debug["lexical"]["raw_score"] == 2.0
    assert result[0].debug["lexical"]["normalized_score"] == 1.0
    assert result[0].debug["vector"]["raw_score"] == 1.0
    assert result[0].debug["vector"]["normalized_score"] == 0.0
    assert result[0].debug["lexical"]["weighted_score"] == 0.7
    assert result[0].debug["vector"]["weighted_score"] == 0.0
    assert result[1].debug["vector"]["normalized_score"] == 1.0
    assert result[1].debug["vector"]["weighted_score"] == 0.3
    assert result[0].debug["combined_score"] == result[0].score


async def test_index_document() -> None:
    """Service should index document with generated embedding."""

    settings = Settings()
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )

    payload = IndexDocumentRequest(
        id="movie-1",
        document={
            "movie": "Inception",
            "overview": "Dreams inside dreams",
        },
    )
    assert await service.index_document(payload=payload) is True


async def test_check_dependencies() -> None:
    """Service should report healthy when both backends are healthy."""

    settings = Settings()
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )
    assert await service.check_dependencies() is True


async def test_bulk_index_documents() -> None:
    """Service should index documents in bulk mode."""

    settings = Settings(BULK_INDEX_BATCH_SIZE=2)
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )

    payloads = [
        IndexDocumentRequest(id="movie-1", document={"movie": "One", "overview": "A"}),
        IndexDocumentRequest(id="movie-2", document={"movie": "Two", "overview": "B"}),
        IndexDocumentRequest(id="movie-3", document={"movie": "Three", "overview": "C"}),
    ]
    indexed_count, failed_ids = await service.index_documents_bulk(payloads=payloads, batch_size=2)
    assert indexed_count == 3
    assert failed_ids == []
