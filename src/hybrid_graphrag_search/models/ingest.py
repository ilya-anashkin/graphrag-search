from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentIngestionRequest(BaseModel):
    doc_id: str = Field(..., description="Unique identifier for the document.")
    title: str = Field(..., description="Title of the document.")
    text: str = Field(..., description="Raw text to ingest.")
    tags: Optional[List[str]] = Field(default=None, description="Optional tags for filtering.")


class DocumentIngestionResponse(BaseModel):
    ingested_docs: int
    ingested_chunks: int
    timing: Dict[str, float]
