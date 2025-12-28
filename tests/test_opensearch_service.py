from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from hybrid_graphrag_search.services.opensearch_service import OpenSearchIndexService
from hybrid_graphrag_search.settings import Settings


@pytest.fixture
def settings() -> Settings:
    s = Settings()
    s.embedding_dimension = 3
    s.opensearch_index = "test-index"
    return s


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.indices = MagicMock()
    return mock


def test_create_index_if_not_exists_creates_when_missing(client: MagicMock, settings: Settings):
    client.indices.exists.return_value = False
    service = OpenSearchIndexService(client, settings)

    service.create_index_if_not_exists()

    client.indices.create.assert_called_once()
    args, kwargs = client.indices.create.call_args
    assert kwargs["index"] == settings.opensearch_index
    assert kwargs["body"]["mappings"]["properties"]["embedding"]["dimension"] == settings.embedding_dimension


def test_search_bm25_builds_filter(client: MagicMock, settings: Settings):
    client.search.return_value = {"hits": {"hits": [{"_id": "1"}]}}
    service = OpenSearchIndexService(client, settings)

    results = service.search_bm25("hello", k=5, filters={"tags": "demo"})

    assert results[0]["_id"] == "1"
    client.search.assert_called_once()
    _, kwargs = client.search.call_args
    body: Dict[str, Any] = kwargs["body"]
    assert {"term": {"tags": "demo"}} in body["query"]["bool"]["filter"]


def test_search_knn_uses_num_candidates(client: MagicMock, settings: Settings):
    client.search.return_value = {"hits": {"hits": [{"_id": "2"}]}}
    service = OpenSearchIndexService(client, settings)
    results = service.search_knn([0.1, 0.2, 0.3], k=3, filters=None)
    assert results[0]["_id"] == "2"
    _, kwargs = client.search.call_args
    body: Dict[str, Any] = kwargs["body"]
    assert body["knn"]["num_candidates"] >= 3


def test_get_by_ids_returns_docs(client: MagicMock, settings: Settings):
    client.mget.return_value = {"docs": [{"_id": "doc-1"}]}
    service = OpenSearchIndexService(client, settings)
    docs = service.get_by_ids(["doc-1"])
    assert docs == [{"_id": "doc-1"}]
