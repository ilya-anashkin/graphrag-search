from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from ..settings import Settings

logger = logging.getLogger(__name__)


class OpenSearchIndexService:
    """Service for BM25 and vector indexing in OpenSearch."""

    def __init__(self, client: OpenSearch, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        logger.debug(
            "Initialized OpenSearchIndexService with index %s", self.settings.opensearch_index
        )

    def create_index_if_not_exists(self, index_name: Optional[str] = None) -> None:
        index = index_name or self.settings.opensearch_index
        exists = self.client.indices.exists(index=index)
        if exists:
            logger.info("Index %s already exists", index)
            return
        logger.info("Creating index %s", index)
        body = self._index_body()
        self.client.indices.create(index=index, body=body)
        logger.info("Index %s created with mapping", index)

    def index_documents(
        self, documents: List[Dict[str, Any]], index_name: Optional[str] = None
    ) -> None:
        index = index_name or self.settings.opensearch_index
        if not documents:
            logger.warning("index_documents called with empty batch")
            return
        logger.info("Indexing %d documents into %s", len(documents), index)
        actions = [
            {"_index": index, "_id": doc.get("chunk_id") or doc.get("doc_id"), "_source": doc}
            for doc in documents
        ]
        bulk(self.client, actions, refresh=True)

    def search_bm25(
        self,
        query: str,
        k: int,
        filters: Optional[Dict[str, Any]] = None,
        index_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        index = index_name or self.settings.opensearch_index
        logger.info("Executing BM25 search on %s for '%s'", index, query)
        filter_clauses = self._build_filter_clauses(filters)
        body: Dict[str, Any] = {
            "size": k,
            "query": {
                "bool": {
                    "must": {"multi_match": {"query": query, "fields": ["title", "body"]}},
                    "filter": filter_clauses,
                }
            },
        }
        response = self.client.search(index=index, body=body)
        return response.get("hits", {}).get("hits", [])

    def search_knn(
        self,
        embedding_vector: List[float],
        k: int,
        filters: Optional[Dict[str, Any]] = None,
        index_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        index = index_name or self.settings.opensearch_index
        logger.info("Executing kNN search on %s", index)
        filter_clauses = self._build_filter_clauses(filters)
        body: Dict[str, Any] = {
            "size": k,
            "knn": {
                "field": "embedding",
                "query_vector": embedding_vector,
                "k": k,
                "num_candidates": max(k * 2, 50),
                "filter": filter_clauses,
            },
        }
        response = self.client.search(index=index, body=body)
        return response.get("hits", {}).get("hits", [])

    def get_by_ids(self, ids: List[str], index_name: Optional[str] = None) -> List[Dict[str, Any]]:
        index = index_name or self.settings.opensearch_index
        if not ids:
            return []
        logger.info("Fetching %d documents by id from %s", len(ids), index)
        body = {"ids": ids}
        response = self.client.mget(index=index, body=body)
        return response.get("docs", [])

    def _build_filter_clauses(self, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not filters:
            return []
        return [{"term": {key: value}} for key, value in filters.items()]

    def _index_body(self) -> Dict[str, Any]:
        return {
            "settings": {
                "index": {
                    "knn": True,
                }
            },
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "body": {"type": "text"},
                    "tags": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.settings.embedding_dimension,
                    },
                }
            },
        }
