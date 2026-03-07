"""Embedding service tests."""

import pytest

from app.core.config import Settings
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError


@pytest.mark.asyncio
async def test_ollama_embed_from_embed_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama provider should parse /api/embed response format."""

    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL="qwen3-embedding:latest",
        EMBEDDING_DIMENSION=4,
        EMBEDDING_NORMALIZE=False,
    )
    service = EmbeddingService(settings=settings)

    async def fake_request_once(
        client: object,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        assert path == settings.ollama_embedding_endpoint
        assert payload["model"] == settings.embedding_model
        assert payload["input"] == ["hello"]
        return {"embeddings": [[0.1, 0.2, 0.3, 0.4]]}

    monkeypatch.setattr(service, "_request_ollama_once", fake_request_once)
    vector = await service.embed_text("hello")
    await service.close()

    assert vector == [0.1, 0.2, 0.3, 0.4]


@pytest.mark.asyncio
async def test_ollama_embed_from_legacy_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama provider should parse legacy /api/embeddings response format."""

    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL="qwen3-embedding:latest",
        EMBEDDING_DIMENSION=4,
        EMBEDDING_NORMALIZE=False,
    )
    service = EmbeddingService(settings=settings)

    async def fake_request_once(
        client: object,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        raise EmbeddingServiceError("primary endpoint failed")

    async def fake_request(
        path: str,
        payload: dict[str, object],
        fallback_path: str | None = None,
        fallback_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        assert path == settings.ollama_embedding_endpoint
        assert fallback_path == settings.ollama_embedding_legacy_endpoint
        return {"embedding": [0.5, 0.6, 0.7, 0.8]}

    monkeypatch.setattr(service, "_request_ollama_once", fake_request_once)
    monkeypatch.setattr(service, "_request_ollama", fake_request)
    vector = await service.embed_text("hello")
    await service.close()

    assert vector == [0.5, 0.6, 0.7, 0.8]


@pytest.mark.asyncio
async def test_ollama_embed_dimension_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama provider should raise on unexpected embedding dimension."""

    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL="qwen3-embedding:latest",
        EMBEDDING_DIMENSION=3,
        EMBEDDING_NORMALIZE=False,
    )
    service = EmbeddingService(settings=settings)

    async def fake_request_once(
        client: object,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return {"embeddings": [[0.1, 0.2, 0.3, 0.4]]}

    monkeypatch.setattr(service, "_request_ollama_once", fake_request_once)
    with pytest.raises(EmbeddingServiceError):
        await service.embed_text("hello")
    await service.close()
