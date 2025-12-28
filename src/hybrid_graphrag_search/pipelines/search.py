from __future__ import annotations

import logging
from typing import List

from ..models import SearchHit, SearchRequest, SearchResponse
from ..services import EmbeddingService, GraphService, OpenSearchIndexService

logger = logging.getLogger(__name__)


class SearchPipeline:
    """Pipeline coordinating hybrid retrieval and graph expansion."""

    def __init__(
        self,
        opensearch_service: OpenSearchIndexService,
        graph_service: GraphService,
        embedding_service: EmbeddingService,
    ) -> None:
        self.opensearch_service = opensearch_service
        self.graph_service = graph_service
        self.embedding_service = embedding_service
        logger.debug("SearchPipeline initialized.")

    def search(self, request: SearchRequest) -> SearchResponse:
        logger.info("Search pipeline placeholder executing for query='%s'", request.query)
        # Placeholder workflow: in the final version, embed the query, run BM25 and kNN,
        # merge scores, expand graph neighbors, and re-rank.
        logger.debug(
            "Hybrid retrieval (BM25 + vector) and graph expansion logic not yet implemented."
        )
        placeholder_results: List[SearchHit] = []
        return SearchResponse(query=request.query, results=placeholder_results)
