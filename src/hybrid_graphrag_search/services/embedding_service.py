from __future__ import annotations

import logging
from typing import List, Optional

from sentence_transformers import SentenceTransformer

from ..settings import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for encoding text into dense embeddings."""

    def __init__(self, model: Optional[SentenceTransformer], settings: Settings) -> None:
        self.model = model
        self.settings = settings
        logger.debug(
            "Initialized EmbeddingService with model %s", self.settings.embedding_model_name
        )

    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        if not self.model:
            raise RuntimeError("Embedding model is not initialized.")
        logger.info("Encoding %d chunks", len(chunks))
        vectors = self.model.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)
        return [vec.tolist() for vec in vectors]
