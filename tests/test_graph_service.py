from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from hybrid_graphrag_search.services.graph_service import GraphService
from hybrid_graphrag_search.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def driver() -> MagicMock:
    session = MagicMock()
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    driver = MagicMock()
    driver.session.return_value = session
    return driver


def test_ensure_constraints_calls_queries(driver: MagicMock, settings: Settings):
    service = GraphService(driver, settings)
    service.ensure_constraints()
    session = driver.session.return_value
    assert session.execute_write.call_count == 2


def test_upsert_chunks_runs_unwind(driver: MagicMock, settings: Settings):
    service = GraphService(driver, settings)
    chunks: List[Dict[str, Any]] = [
        {"chunk_id": "c1", "doc_id": "d1", "title": "t1"},
        {"chunk_id": "c2", "doc_id": "d1", "title": "t2"},
    ]
    service.upsert_chunks(chunks)
    session = driver.session.return_value
    session.execute_write.assert_called_once()


def test_link_next_edges_builds_pairs(driver: MagicMock, settings: Settings):
    service = GraphService(driver, settings)
    service.link_next_edges("doc", ["c1", "c2", "c3"])
    session = driver.session.return_value
    session.execute_write.assert_called_once()


def test_expand_neighbors_returns_data(driver: MagicMock, settings: Settings):
    session = driver.session.return_value
    session.execute_read.return_value = [{"seed_id": "c1", "neighbor_chunk_id": "c2", "via_edges": ["NEXT"]}]
    service = GraphService(driver, settings)
    res = service.expand_neighbors(["c1"], hops=1, limit_per_seed=5)
    assert res[0]["neighbor_chunk_id"] == "c2"


def test_get_subgraph_returns_nodes_edges(driver: MagicMock, settings: Settings):
    session = driver.session.return_value
    session.execute_read.side_effect = [
        [{"chunk_id": "c1", "doc_id": "d1", "title": "t1"}],
        [{"source": "c1", "target": "c2", "type": "NEXT"}],
    ]
    service = GraphService(driver, settings)
    res = service.get_subgraph(["c1"], hops=1)
    assert "nodes" in res and "edges" in res
