from typing import Any
from unittest.mock import MagicMock

from hybrid_graphrag_search.models import DocumentIngestionRequest
from hybrid_graphrag_search.pipelines.ingestion import IngestionPipeline
from hybrid_graphrag_search.settings import Settings


class _DummyService:
    def __getattr__(self, item: str) -> Any:  # pragma: no cover - placeholder
        raise NotImplementedError


def test_chunking_respects_overlap():
    settings = Settings()
    settings.chunk_size = 10
    settings.chunk_overlap = 2
    pipeline = IngestionPipeline(_DummyService(), _DummyService(), _DummyService(), settings)
    chunks = pipeline.chunk_text("abcdefghijk")
    assert len(chunks) == 2
    assert chunks[0] == "abcdefghij"
    assert chunks[1].startswith("ij")


def test_ingest_document_calls_services(monkeypatch):
    settings = Settings()
    settings.chunk_size = 5
    settings.chunk_overlap = 1

    os_service = MagicMock()
    graph_service = MagicMock()
    embed_service = MagicMock()
    embed_service.embed_chunks.return_value = [[0.1, 0.2], [0.2, 0.3]]

    pipeline = IngestionPipeline(os_service, graph_service, embed_service, settings)
    req = DocumentIngestionRequest(doc_id="d1", title="t", text="abcdefgh", tags=["x"])
    resp = pipeline.ingest_document(req)

    assert resp.ingested_docs == 1
    assert resp.ingested_chunks > 0
    assert os_service.index_documents.called
    assert graph_service.upsert_chunks.called
    assert graph_service.link_next_edges.called
