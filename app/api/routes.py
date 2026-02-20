"""HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.logging import request_id_context
from app.models.schemas import (
    HealthResponse,
    IndexDocumentRequest,
    IndexDocumentsBulkRequest,
    IndexDocumentsBulkResponse,
    IndexDocumentResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.search_service import SearchService

router = APIRouter()


def get_search_service() -> SearchService:
    """Dependency placeholder overridden in application startup."""

    raise RuntimeError("SearchService dependency is not configured")


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    """Liveness probe endpoint."""

    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse)
async def ready(search_service: SearchService = Depends(get_search_service)) -> HealthResponse:
    """Readiness probe endpoint with dependencies check."""

    is_ready = await search_service.check_dependencies()
    return HealthResponse(status="ok" if is_ready else "degraded")


@router.post("/search", response_model=SearchResponse)
async def search(payload: SearchRequest, search_service: SearchService = Depends(get_search_service)) -> SearchResponse:
    """Search endpoint."""

    items = await search_service.search(
        query=payload.query,
        limit=payload.limit,
        lexical_weight=payload.lexical_weight,
        vector_weight=payload.vector_weight,
    )
    return SearchResponse(request_id=request_id_context.get(), items=items)


@router.post("/documents", response_model=IndexDocumentResponse, status_code=201)
async def index_document(
    payload: IndexDocumentRequest, search_service: SearchService = Depends(get_search_service)
) -> IndexDocumentResponse:
    """Document indexing endpoint."""

    is_indexed = await search_service.index_document(payload=payload)
    if not is_indexed:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Document indexing failed.",
        )

    return IndexDocumentResponse(request_id=request_id_context.get(), id=payload.id, status="indexed")


@router.post("/documents/bulk", response_model=IndexDocumentsBulkResponse)
async def index_documents_bulk(
    payload: IndexDocumentsBulkRequest, search_service: SearchService = Depends(get_search_service)
) -> IndexDocumentsBulkResponse:
    """Bulk document indexing endpoint."""

    indexed, failed_ids = await search_service.index_documents_bulk(
        payloads=payload.items,
        batch_size=payload.batch_size,
    )
    total = len(payload.items)
    return IndexDocumentsBulkResponse(
        request_id=request_id_context.get(),
        total=total,
        indexed=indexed,
        failed=total - indexed,
        failed_ids=failed_ids,
    )
