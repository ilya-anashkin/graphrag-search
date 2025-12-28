from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query.")
    top_k: int = Field(5, description="Number of results to return.")


class SearchHit(BaseModel):
    doc_id: str
    score: float
    source: Dict[str, Any]
    explanation: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchHit]
    detail: str = "Search pipeline placeholder executed."
