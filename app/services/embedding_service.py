"""Embedding service with provider-based implementation."""

import asyncio
import hashlib
import math
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed

from app.core.config import Settings
from app.core.logging import get_logger

EMBEDDING_PROVIDER_LOCAL = "local"
EMBEDDING_PROVIDER_HASH = "hash"
EMBEDDING_PROVIDER_OLLAMA = "ollama"
MAX_UINT32 = 4294967295.0
OLLAMA_EMBED_RESPONSE_KEY = "embeddings"
OLLAMA_EMBEDDING_RESPONSE_KEY = "embedding"
OLLAMA_INPUT_KEY = "input"
OLLAMA_PROMPT_KEY = "prompt"
OLLAMA_MODEL_KEY = "model"


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
        self._ollama_client: httpx.AsyncClient | None = None

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

        if self._provider == EMBEDDING_PROVIDER_OLLAMA:
            await self._embed_ollama(text="warmup")
            self._logger.info(
                "embedding_model_loaded",
                provider=self._provider,
                model=self._settings.embedding_model,
                base_url=self._settings.ollama_base_url,
                endpoint=self._settings.ollama_embedding_endpoint,
                dimension=self._settings.embedding_dimension,
            )
            return

        self._logger.info(
            "embedding_preload_skipped",
            reason="provider_without_model_load",
            provider=self._provider,
        )

    async def close(self) -> None:
        """Close internal resources."""

        self._local_model = None
        if self._ollama_client is not None:
            await self._ollama_client.aclose()
            self._ollama_client = None

    async def embed_text(self, text: str) -> list[float]:
        """Build dense vector from text."""

        vectors = await self.embed_texts([text])
        return vectors[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Build dense vectors for multiple texts."""

        if not texts:
            return []

        if self._provider == EMBEDDING_PROVIDER_HASH:
            return [self._embed_hash(text=text) for text in texts]

        if self._provider == EMBEDDING_PROVIDER_LOCAL:
            model = await self._get_local_model()
            return await asyncio.to_thread(self._embed_local_batch_sync, model, texts)

        if self._provider == EMBEDDING_PROVIDER_OLLAMA:
            return await self._embed_ollama_batch(texts=texts)

        raise EmbeddingServiceError(f"Unsupported embedding provider: {self._provider}")

    async def _get_local_model(self) -> Any:
        """Lazily load local sentence-transformers model."""

        if self._local_model is not None:
            return self._local_model

        async with self._local_model_lock:
            if self._local_model is not None:
                return self._local_model

            self._local_model = await asyncio.to_thread(
                self._load_sentence_transformer_model
            )
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

        vectors = self._embed_local_batch_sync(model=model, texts=[text])
        return vectors[0]

    def _embed_local_batch_sync(
        self, model: Any, texts: list[str]
    ) -> list[list[float]]:
        """Encode multiple texts with sentence-transformers model."""

        matrix = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=self._settings.embedding_normalize,
        )
        rows = matrix.tolist()
        if not isinstance(rows, list):
            raise EmbeddingServiceError("Local model returned invalid embedding matrix")
        return [
            self._finalize_vector(values=[float(value) for value in row])
            for row in rows
        ]

    async def _embed_ollama(self, text: str) -> list[float]:
        """Encode text with Ollama HTTP API."""

        vectors = await self._embed_ollama_batch(texts=[text])
        return vectors[0]

    async def _embed_ollama_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts with Ollama HTTP API."""

        non_empty_texts = [text for text in texts if text.strip()]
        if len(non_empty_texts) != len(texts):
            raise EmbeddingServiceError("Input texts for embedding must be non-empty")

        payload = {
            OLLAMA_MODEL_KEY: self._settings.embedding_model,
            OLLAMA_INPUT_KEY: texts,
        }
        client = self._get_ollama_client()
        try:
            response = await self._request_ollama_once(
                client=client,
                path=self._settings.ollama_embedding_endpoint,
                payload=payload,
            )
            vectors = self._extract_ollama_vectors(
                response=response, expected_count=len(texts)
            )
            return [self._finalize_vector(values=vector) for vector in vectors]
        except EmbeddingServiceError as error:
            self._logger.warning(
                "ollama_batch_embedding_failed_fallback_to_single",
                error=str(error),
                batch_size=len(texts),
            )
            vectors: list[list[float]] = []
            for text in texts:
                response = await self._request_ollama(
                    path=self._settings.ollama_embedding_endpoint,
                    payload={
                        OLLAMA_MODEL_KEY: self._settings.embedding_model,
                        OLLAMA_INPUT_KEY: [text],
                    },
                    fallback_path=self._settings.ollama_embedding_legacy_endpoint,
                    fallback_payload={
                        OLLAMA_MODEL_KEY: self._settings.embedding_model,
                        OLLAMA_PROMPT_KEY: text,
                    },
                )
                vector = self._extract_ollama_vectors(
                    response=response, expected_count=1
                )[0]
                vectors.append(self._finalize_vector(values=vector))
            return vectors

    async def _request_ollama(
        self,
        path: str,
        payload: dict[str, Any],
        fallback_path: str | None = None,
        fallback_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform Ollama embedding request with retries and optional fallback endpoint."""

        client = self._get_ollama_client()

        try:
            return await self._request_ollama_once(
                client=client, path=path, payload=payload
            )
        except EmbeddingServiceError:
            if fallback_path is None or fallback_payload is None:
                raise
            return await self._request_ollama_once(
                client=client, path=fallback_path, payload=fallback_payload
            )

    async def _request_ollama_once(
        self,
        client: httpx.AsyncClient,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute single Ollama API call with retry policy."""

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._settings.retry_attempts),
            wait=wait_fixed(self._settings.retry_wait_seconds),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await client.post(path, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict):
                        raise EmbeddingServiceError(
                            "Ollama response must be a JSON object"
                        )
                    return body
                except httpx.HTTPStatusError as error:
                    if error.response.status_code == 404:
                        raise EmbeddingServiceError(
                            f"Ollama endpoint not found: {path}"
                        ) from error
                    raise EmbeddingServiceError(
                        f"Ollama HTTP error: {error}"
                    ) from error
                except httpx.HTTPError as error:
                    raise EmbeddingServiceError(
                        f"Ollama request failed: {error}"
                    ) from error
                except ValueError as error:
                    raise EmbeddingServiceError(
                        f"Ollama returned invalid JSON: {error}"
                    ) from error

        raise EmbeddingServiceError("Ollama request failed after retries")

    def _extract_ollama_vectors(
        self, response: dict[str, Any], expected_count: int
    ) -> list[list[float]]:
        """Extract embedding vectors from Ollama response payload."""

        if OLLAMA_EMBED_RESPONSE_KEY in response:
            values = response.get(OLLAMA_EMBED_RESPONSE_KEY)
            if not isinstance(values, list) or not values:
                raise EmbeddingServiceError(
                    "Ollama /api/embed returned empty embeddings list"
                )
            if len(values) != expected_count:
                raise EmbeddingServiceError(
                    "Ollama /api/embed embeddings count mismatch. "
                    f"Expected {expected_count}, got {len(values)}"
                )
            if not all(isinstance(item, list) for item in values):
                raise EmbeddingServiceError(
                    "Ollama /api/embed returned invalid embedding format"
                )
            return [[float(value) for value in item] for item in values]

        if OLLAMA_EMBEDDING_RESPONSE_KEY in response:
            values = response.get(OLLAMA_EMBEDDING_RESPONSE_KEY)
            if not isinstance(values, list):
                raise EmbeddingServiceError(
                    "Ollama /api/embeddings returned invalid embedding format"
                )
            if expected_count != 1:
                raise EmbeddingServiceError(
                    "Legacy /api/embeddings endpoint does not support batch mode"
                )
            return [[float(value) for value in values]]

        raise EmbeddingServiceError("Ollama response does not contain embedding vector")

    def _finalize_vector(self, values: list[float]) -> list[float]:
        """Normalize and validate embedding vector according to service settings."""

        if self._settings.embedding_normalize:
            values = self._normalize(values=values)
        self._validate_dimension(values=values)
        return values

    def _validate_dimension(self, values: list[float]) -> None:
        """Validate embedding vector dimension against configuration."""

        if len(values) != self._settings.embedding_dimension:
            raise EmbeddingServiceError(
                "Embedding dimension mismatch. "
                f"Expected {self._settings.embedding_dimension}, got {len(values)}"
            )

    def _normalize(self, values: list[float]) -> list[float]:
        """L2 normalize vector values."""

        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            return values
        return [value / norm for value in values]

    def _get_ollama_client(self) -> httpx.AsyncClient:
        """Get or create shared Ollama HTTP client."""

        if self._ollama_client is None:
            self._ollama_client = httpx.AsyncClient(
                base_url=self._settings.ollama_base_url,
                timeout=self._settings.embedding_timeout_seconds,
            )
        return self._ollama_client

    def _embed_hash(self, text: str) -> list[float]:
        """Build deterministic normalized vector from text."""

        values = [0.0] * self._settings.embedding_dimension
        text_bytes = text.encode("utf-8")

        for index in range(self._settings.embedding_dimension):
            digest = hashlib.sha256(text_bytes + str(index).encode("utf-8")).digest()
            values[index] = (
                int.from_bytes(digest[:4], byteorder="big", signed=False) / MAX_UINT32
            )

        return self._finalize_vector(values=values)
