"""Request and response schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Incoming search payload."""

    query: str = Field(..., min_length=1, description="User query string.")
    limit: int = Field(
        default=10, ge=1, le=100, description="Maximum number of results."
    )
    lexical_weight: float | None = Field(
        default=None, ge=0.0, description="Lexical score weight."
    )
    vector_weight: float | None = Field(
        default=None, ge=0.0, description="Vector score weight."
    )
    search_mode: Literal[
        "lexical",
        "lexical_vector",
        "lexical_vector_graph",
    ] = Field(
        default="lexical_vector_graph",
        description="Enabled search channels and graph enrichment mode.",
    )


class SearchItem(BaseModel):
    """Unified search item from mixed backends."""

    source: str = Field(..., description="Result source system.")
    id: str = Field(..., description="Result id.")
    score: float = Field(..., description="Normalized relevance score.")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Source-specific payload."
    )
    debug: dict[str, Any] = Field(
        default_factory=dict, description="Per-channel scoring debug information."
    )


class SearchResponse(BaseModel):
    """Search response payload."""

    request_id: str = Field(..., description="Correlation request id.")
    items: list[SearchItem] = Field(default_factory=list, description="Search results.")


class IndexDocumentRequest(BaseModel):
    """Incoming payload for document indexing."""

    id: str = Field(..., min_length=1, description="Document identifier.")
    document: dict[str, Any] = Field(
        default_factory=dict, description="Domain-specific document payload."
    )


class IndexDocumentResponse(BaseModel):
    """Document indexing response payload."""

    request_id: str = Field(..., description="Correlation request id.")
    id: str = Field(..., description="Document identifier.")
    status: str = Field(..., description="Document indexing status.")


class IndexDocumentsBulkRequest(BaseModel):
    """Incoming bulk indexing payload."""

    items: list[IndexDocumentRequest] = Field(
        default_factory=list, description="Documents for bulk indexing."
    )


class IndexDocumentsBulkResponse(BaseModel):
    """Bulk indexing response payload."""

    request_id: str = Field(..., description="Correlation request id.")
    total: int = Field(..., description="Total number of received documents.")
    indexed: int = Field(..., description="Number of successfully indexed documents.")
    failed: int = Field(..., description="Number of failed documents.")
    failed_ids: list[str] = Field(
        default_factory=list, description="Identifiers of failed documents."
    )


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str = Field(..., description="Service health status.")


class AskRequest(BaseModel):
    """Incoming request for LLM answer generation."""

    question: str = Field(..., min_length=1, description="User question for LLM.")
    items: list[SearchItem] = Field(
        default_factory=list, description="Search results context for answer."
    )


class AskResponse(BaseModel):
    """LLM answer response payload."""

    request_id: str = Field(..., description="Correlation request id.")
    answer: str = Field(..., description="Generated answer.")
    think: str | None = Field(
        default=None, description="Model internal reasoning text for debugging."
    )
    model: str = Field(..., description="Model used for generation.")
    used_items: int = Field(
        ..., description="Number of context items provided to the model."
    )
