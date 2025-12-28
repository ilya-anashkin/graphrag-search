from __future__ import annotations

import logging
from typing import Annotated, List, Union

from fastapi import APIRouter, Body, Depends, HTTPException, status
from neo4j import Driver
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer

from ..api import deps
from ..models import (
    DocumentIngestionRequest,
    DocumentIngestionResponse,
    SearchRequest,
    SearchResponse,
)
from ..pipelines import IngestionPipeline, SearchPipeline
from ..services import EmbeddingService, GraphService, OpenSearchIndexService
from ..settings import Settings, get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


def get_opensearch_service(
    client: OpenSearch = Depends(deps.opensearch_dep),
    settings: Settings = Depends(get_settings),
) -> OpenSearchIndexService:
    return OpenSearchIndexService(client, settings)


def get_graph_service(
    driver: Driver = Depends(deps.graph_driver_dep),
    settings: Settings = Depends(get_settings),
) -> GraphService:
    return GraphService(driver, settings)


def get_embedding_service(
    model: SentenceTransformer = Depends(deps.embedding_model_dep),
    settings: Settings = Depends(get_settings),
) -> EmbeddingService:
    return EmbeddingService(model, settings)


def get_ingestion_pipeline(
    opensearch_service: Annotated[OpenSearchIndexService, Depends(get_opensearch_service)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestionPipeline:
    return IngestionPipeline(opensearch_service, graph_service, embedding_service, settings)


def get_search_pipeline(
    opensearch_service: Annotated[OpenSearchIndexService, Depends(get_opensearch_service)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> SearchPipeline:
    return SearchPipeline(opensearch_service, graph_service, embedding_service)


@router.post(
    "/ingest",
    response_model=DocumentIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_document(
    pipeline: Annotated[IngestionPipeline, Depends(get_ingestion_pipeline)],
    request: Union[DocumentIngestionRequest, List[DocumentIngestionRequest]] = Body(
        ...,
        examples={
            "single": {
                "summary": "Single document",
                "value": {
                    "doc_id": "doc-1",
                    "title": "Demo Doc",
                    "text": "Sample text to ingest.",
                    "tags": ["demo", "test"],
                },
            },
            "batch": {
                "summary": "Batch documents",
                "value": [
                    {
                        "doc_id": "doc-1",
                        "title": "Demo Doc",
                        "text": "Sample text to ingest.",
                        "tags": ["demo", "test"],
                    },
                    {
                        "doc_id": "doc-2",
                        "title": "Second Doc",
                        "text": "More text to ingest.",
                        "tags": ["demo"],
                    },
                ],
            },
        },
    ),
) -> DocumentIngestionResponse:
    try:
        return pipeline.ingest_document(request)
    except NotImplementedError as exc:
        logger.exception("Ingestion pipeline not implemented")
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - runtime safeguard
        logger.exception("Unexpected error during ingestion")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
)
def search(
    pipeline: Annotated[SearchPipeline, Depends(get_search_pipeline)],
    request: SearchRequest = Body(
        ...,
        examples={
            "default": {
                "summary": "Search example",
                "value": {"query": "graph retrieval", "top_k": 5},
            }
        },
    ),
) -> SearchResponse:
    try:
        return pipeline.search(request)
    except NotImplementedError as exc:
        logger.exception("Search pipeline not implemented")
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
