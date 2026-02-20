"""API tests."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_search_service
from app.core.config import get_settings
from app.main import create_app
from app.models.schemas import SearchItem


class FakeSearchService:
    """Fake service for API tests."""

    async def search(
        self,
        query: str,
        limit: int,
        lexical_weight: float | None = None,
        vector_weight: float | None = None,
    ) -> list[SearchItem]:
        """Return deterministic fake results."""

        return [
            SearchItem(
                source="fake",
                id="1",
                score=1.0,
                payload={"query": query, "limit": str(limit)},
            )
        ]

    async def check_dependencies(self) -> bool:
        """Return healthy dependencies state."""

        return True

    async def index_document(self, payload: Any) -> bool:
        """Return successful indexing state."""

        return True

    async def index_documents_bulk(self, payloads: list[Any], batch_size: int | None = None) -> tuple[int, list[str]]:
        """Return successful bulk indexing state."""

        return len(payloads), []


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build test client with fake service dependency."""

    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_search_service] = lambda: FakeSearchService()
    return TestClient(app)


def test_live_health(client: TestClient) -> None:
    """Verify liveness endpoint."""

    response = client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_health(client: TestClient) -> None:
    """Verify readiness endpoint."""

    response = client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search(client: TestClient) -> None:
    """Verify search endpoint returns request id and results."""

    payload: dict[str, Any] = {"query": "test", "limit": 1}
    response = client.post("/v1/search", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["source"] == "fake"
    assert "debug" in data["items"][0]


def test_index_document(client: TestClient) -> None:
    """Verify document indexing endpoint."""

    payload: dict[str, Any] = {
        "id": "movie-1",
        "document": {
            "rating": 1,
            "movie": "Inception",
            "year": 2010,
            "country": "USA",
            "rating_ball": 8.8,
            "overview": "Dreams inside dreams.",
            "director": "Christopher Nolan",
            "screenwriter": "Christopher Nolan",
            "actors": "Leonardo DiCaprio",
            "url_logo": "https://example.com/logo.jpg"
        },
    }
    response = client.post("/v1/documents", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "movie-1"
    assert data["status"] == "indexed"


def test_index_documents_bulk(client: TestClient) -> None:
    """Verify bulk document indexing endpoint."""

    payload: dict[str, Any] = {
        "items": [
            {"id": "movie-1", "document": {"movie": "Inception"}},
            {"id": "movie-2", "document": {"movie": "Interstellar"}},
        ],
        "batch_size": 2,
    }
    response = client.post("/v1/documents/bulk", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["indexed"] == 2
    assert data["failed"] == 0
