from __future__ import annotations

import logging
import time
from typing import List, Sequence, Union

from ..models import DocumentIngestionRequest, DocumentIngestionResponse
from ..services import EmbeddingService, GraphService, OpenSearchIndexService
from ..settings import Settings

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Pipeline orchestrating chunking, embedding, indexing, and graph writes."""

    def __init__(
        self,
        opensearch_service: OpenSearchIndexService,
        graph_service: GraphService,
        embedding_service: EmbeddingService,
        settings: Settings,
    ) -> None:
        self.opensearch_service = opensearch_service
        self.graph_service = graph_service
        self.embedding_service = embedding_service
        self.settings = settings
        logger.debug("IngestionPipeline initialized.")

    def chunk_text(self, text: str) -> List[str]:
        """Character-based chunker with overlap."""
        size = max(self.settings.chunk_size, 1)
        overlap = max(min(self.settings.chunk_overlap, size - 1), 0)
        chunks: List[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + size, length)
            chunk = text[start:end]
            chunks.append(chunk)
            if end == length:
                break
            start = max(end - overlap, start + 1)
        logger.debug("Chunked text into %d chunks", len(chunks))
        return chunks

    def ingest_document(
        self, request: Union[DocumentIngestionRequest, Sequence[DocumentIngestionRequest]]
    ) -> DocumentIngestionResponse:
        if isinstance(request, list):
            documents = list(request)
        else:
            documents = [request]  # type: ignore[list-item]

        timings: dict[str, float] = {}
        total_chunks = 0
        self._retry("opensearch_create_index", self.opensearch_service.create_index_if_not_exists)

        t0 = time.perf_counter()
        for doc in documents:
            doc_chunks = self.chunk_text(doc.text)
            total_chunks += len(doc_chunks)
            chunk_payloads = self._build_chunk_payloads(doc, doc_chunks)
            embeddings = self.embedding_service.embed_chunks([c["body"] for c in chunk_payloads])
            for payload, embedding in zip(chunk_payloads, embeddings, strict=False):
                payload["embedding"] = embedding
            self._retry("opensearch_index", self.opensearch_service.index_documents, chunk_payloads)
            self._retry(
                "graph_upsert",
                self.graph_service.upsert_chunks,
                [
                    {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "title": c.get("title")}
                    for c in chunk_payloads
                ],
            )
            ordered_ids = [c["chunk_id"] for c in chunk_payloads]
            self._retry(
                "graph_link_next", self.graph_service.link_next_edges, doc.doc_id, ordered_ids
            )
        timings["total_seconds"] = round(time.perf_counter() - t0, 4)

        return DocumentIngestionResponse(
            ingested_docs=len(documents),
            ingested_chunks=total_chunks,
            timing=timings,
        )

    def _build_chunk_payloads(
        self, doc: DocumentIngestionRequest, chunks: List[str]
    ) -> List[dict[str, object]]:
        payloads: List[dict[str, object]] = []
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc.doc_id}-chunk-{idx}"
            payloads.append(
                {
                    "doc_id": doc.doc_id,
                    "chunk_id": chunk_id,
                    "title": doc.title,
                    "body": chunk,
                    "tags": doc.tags,
                    "created_at": now,
                }
            )
        return payloads

    def _retry(self, name: str, fn, *args, **kwargs) -> None:
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                fn(*args, **kwargs)
                return
            except Exception as exc:  # pragma: no cover - runtime guard
                logger.warning("%s attempt %d/%d failed: %s", name, attempt, attempts, exc)
                if attempt == attempts:
                    logger.error("%s failed after %d attempts", name, attempts)
                    raise
