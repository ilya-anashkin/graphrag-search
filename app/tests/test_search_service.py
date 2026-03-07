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

    async def fetch_graph_context(
        self,
        item_ids: list[str],
        person_limit: int = 5,
        related_limit: int = 3,
        shared_people_limit: int = 5,
    ) -> dict[str, dict[str, object]]:
        """Return fake graph context for item ids."""

        return {
            item_id: {
                "connections": [
                    {
                        "entity_type": "Director",
                        "entity": "director-1",
                        "relation": "DIRECTED",
                    },
                    {
                        "entity_type": "Actor",
                        "entity": "actor-1",
                        "relation": "ACTED_IN",
                    },
                ],
                "related_movies": [
                    {
                        "id": f"{item_id}-related-1",
                        "movie": "Related Movie",
                        "shared_people_count": related_limit,
                        "shared_people_relations": [
                            {
                                "person": "actor-1",
                                "source_relation": "ACTED_IN",
                                "related_relation": "ACTED_IN",
                            }
                        ][:shared_people_limit],
                    }
                ],
            }
            for item_id in item_ids
        }

    async def ingest_documents(self, rows: list[dict[str, object]]) -> tuple[list[str], list[str]]:
        """Accept graph ingestion for provided rows."""

        succeeded = [str(row.get("id", "")) for row in rows if str(row.get("id", ""))]
        return succeeded, []

    async def check_health(self) -> bool:
        """Return fake healthy state."""

        return True


class FakeEmbeddingService:
    """Fake embedding service."""

    def __init__(self) -> None:
        """Initialize call counters."""

        self.batch_calls = 0
        self.single_calls = 0

    async def embed_text(self, text: str) -> list[float]:
        """Return deterministic fake embedding."""

        self.single_calls += 1
        return [0.1, 0.2, 0.3]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic fake embeddings for a batch."""

        self.batch_calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def close(self) -> None:
        """No-op close for interface compatibility."""

        return None


class FakeLLMService:
    """Fake LLM service."""

    async def answer_from_items(
        self,
        question: str,
        items: list[SearchItem],
    ) -> dict[str, str | None]:
        """Return deterministic answer."""

        return {"answer": f"llm:{question}:{len(items)}", "think": None}


def build_domain_artifacts() -> DomainArtifacts:
    """Build fake domain artifacts."""

    return DomainArtifacts(
        domain_name="movies",
        index_body={"settings": {}, "mappings": {"properties": {}}},
        search_config=DomainSearchConfig(
            vector_source_fields=["movie", "overview"],
            graph_node_label_movie="Movie",
            graph_node_label_actor="Actor",
            graph_node_label_director="Director",
            graph_node_label_screenwriter="Screenwriter",
            graph_node_label_country="Country",
            graph_rel_acted_in="ACTED_IN",
            graph_rel_directed="DIRECTED",
            graph_rel_wrote="WROTE",
            graph_rel_produced_in="PRODUCED_IN",
            graph_ingest_title_field="movie",
            graph_ingest_overview_field="overview",
            graph_ingest_year_field="year",
            graph_ingest_rating_field="rating",
            graph_ingest_rating_ball_field="rating_ball",
            graph_ingest_url_logo_field="url_logo",
            graph_ingest_country_field="country",
            graph_ingest_director_field="director",
            graph_ingest_screenwriter_field="screenwriter",
            graph_ingest_actor_field="actors",
            llm_domain_schema={"entity": "MovieSearchResult"},
        ),
        templates=DomainTemplates(
            lexical_search="{}",
            vector_search="{}",
            graph_context_query="MATCH (n) RETURN n",
            graph_ingest_query="UNWIND $rows AS row RETURN row.id AS id",
            llm_answer_prompt="{{question}}\n{{context}}",
        ),
    )


async def test_service_hybrid_merge_with_weights() -> None:
    """Service should merge lexical and vector channels by weights."""

    settings = Settings(LEXICAL_SEARCH_WEIGHT=0.7, VECTOR_SEARCH_WEIGHT=0.3)
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        llm_service=FakeLLMService(),
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
    assert "graph" in result[0].payload
    assert "connections" in result[0].payload["graph"]
    assert "related_movies" in result[0].payload["graph"]
    assert "movie" not in result[0].payload["graph"]
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
        llm_service=FakeLLMService(),
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
        llm_service=FakeLLMService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )
    assert await service.check_dependencies() is True


async def test_bulk_index_documents() -> None:
    """Service should index documents in bulk mode."""

    settings = Settings(BULK_INDEX_BATCH_SIZE=2)
    embedding_service = FakeEmbeddingService()
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=embedding_service,
        llm_service=FakeLLMService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )

    payloads = [
        IndexDocumentRequest(id="movie-1", document={"movie": "One", "overview": "A"}),
        IndexDocumentRequest(id="movie-2", document={"movie": "Two", "overview": "B"}),
        IndexDocumentRequest(id="movie-3", document={"movie": "Three", "overview": "C"}),
    ]
    indexed_count, failed_ids = await service.index_documents_bulk(payloads=payloads)
    assert indexed_count == 3
    assert failed_ids == []
    assert embedding_service.batch_calls == 2
    assert embedding_service.single_calls == 0


async def test_answer_from_search_items() -> None:
    """Service should produce LLM answer from search items."""

    settings = Settings()
    service = SearchService(
        opensearch_adapter=FakeOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        llm_service=FakeLLMService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )
    result = await service.answer_from_search_items(
        question="Что посмотреть?",
        items=[SearchItem(source="opensearch", id="movie-1", score=1.0, payload={}, debug={})],
    )
    assert str(result.get("answer", "")).startswith("llm:")


async def test_search_filters_lexical_only_when_vector_enabled() -> None:
    """Service should remove lexical-only items when vector channel is enabled."""

    class LexicalOnlyOpenSearchAdapter(FakeOpenSearchAdapter):
        async def lexical_search(self, query: str, limit: int) -> list[dict[str, object]]:
            return [
                {
                    "source": "opensearch",
                    "id": "doc-lex-only",
                    "score": 3.0,
                    "payload": {"title": "lex-only"},
                    "search_type": "lexical",
                }
            ]

        async def vector_search(
            self, query_vector: list[float], limit: int
        ) -> list[dict[str, object]]:
            return []

    settings = Settings(LEXICAL_SEARCH_WEIGHT=0.6, VECTOR_SEARCH_WEIGHT=0.4)
    service = SearchService(
        opensearch_adapter=LexicalOnlyOpenSearchAdapter(),
        neo4j_adapter=FakeNeo4jAdapter(),
        embedding_service=FakeEmbeddingService(),
        llm_service=FakeLLMService(),
        settings=settings,
        domain_artifacts=build_domain_artifacts(),
    )
    result = await service.search(query="abc", limit=10)
    assert result == []
