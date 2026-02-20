"""Embedding service with provider-based implementation."""

import asyncio
import hashlib
import math
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

EMBEDDING_PROVIDER_LOCAL = "local"
EMBEDDING_PROVIDER_HASH = "hash"
MAX_UINT32 = 4294967295.0


class EmbeddingServiceError(Exception):
    """Embedding service exception."""


class EmbeddingService:
    """Build embeddings using configured provider."""

    def __init__(self, settings: Settings) -> None:
        """Initialize embedding service with settings."""

        self._settings = settings
        self._provider = settings.embedding_provider.lower().strip()
        self._logger = get_logger(__name__)
        self._local_model: Any | None = None
        self._local_model_lock = asyncio.Lock()

    async def preload_model(self) -> None:
        """Preload embedding model during startup if enabled."""

        if not self._settings.embedding_preload_on_startup:
            self._logger.info("embedding_preload_skipped", reason="disabled_by_config")
            return

        if self._provider == EMBEDDING_PROVIDER_LOCAL:
            await self._get_local_model()
            self._logger.info(
                "embedding_model_loaded",
                provider=self._provider,
                model=self._settings.embedding_model,
                device=self._settings.embedding_device,
                dimension=self._settings.embedding_dimension,
            )
            return

        self._logger.info("embedding_preload_skipped", reason="provider_without_model_load", provider=self._provider)

    async def close(self) -> None:
        """Close internal resources."""

        self._local_model = None

    async def embed_text(self, text: str) -> list[float]:
        """Build dense vector from text."""

        if self._provider == EMBEDDING_PROVIDER_HASH:
            return self._embed_hash(text=text)

        if self._provider == EMBEDDING_PROVIDER_LOCAL:
            model = await self._get_local_model()
            return await asyncio.to_thread(self._embed_local_sync, model, text)

        raise EmbeddingServiceError(f"Unsupported embedding provider: {self._provider}")

    async def _get_local_model(self) -> Any:
        """Lazily load local sentence-transformers model."""

        if self._local_model is not None:
            return self._local_model

        async with self._local_model_lock:
            if self._local_model is not None:
                return self._local_model

            self._local_model = await asyncio.to_thread(self._load_sentence_transformer_model)
            return self._local_model

    def _load_sentence_transformer_model(self) -> Any:
        """Create sentence-transformers model instance."""

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise EmbeddingServiceError(
                "sentence-transformers is required for local embedding provider"
            ) from error

        return SentenceTransformer(
            self._settings.embedding_model,
            device=self._settings.embedding_device,
        )

    def _embed_local_sync(self, model: Any, text: str) -> list[float]:
        """Encode text with sentence-transformers model."""

        vector = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self._settings.embedding_normalize,
        )
        values = [float(value) for value in vector.tolist()]

        if len(values) != self._settings.embedding_dimension:
            raise EmbeddingServiceError(
                "Embedding dimension mismatch. "
                f"Expected {self._settings.embedding_dimension}, got {len(values)}"
            )
        return values

    def _embed_hash(self, text: str) -> list[float]:
        """Build deterministic normalized vector from text."""

        values = [0.0] * self._settings.embedding_dimension
        text_bytes = text.encode("utf-8")

        for index in range(self._settings.embedding_dimension):
            digest = hashlib.sha256(text_bytes + str(index).encode("utf-8")).digest()
            values[index] = int.from_bytes(digest[:4], byteorder="big", signed=False) / MAX_UINT32

        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            return values
        return [value / norm for value in values]
