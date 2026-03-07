"""FastAPI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from app.adapters.neo4j_client import Neo4jAdapter
from app.adapters.opensearch_client import OpenSearchAdapter
from app.api.routes import get_search_service, router
from app.core.config import Settings, get_settings
from app.core.domain_loader import DomainLoader
from app.core.logging import configure_logging, get_logger
from app.core.request_id import request_id_middleware
from app.frontend.routes import STATIC_DIR
from app.frontend.routes import router as frontend_router
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService


class AppContainer:
    """Application dependency container."""

    def __init__(self, settings: Settings) -> None:
        """Initialize shared dependencies."""

        self.settings = settings
        self._logger = get_logger(__name__)

        domain_loader = DomainLoader(
            domain_root=settings.domains_root, domain_name=settings.domain_name
        )
        self.domain_artifacts = domain_loader.load()

        self._logger.info(
            "domain_artifacts_loaded",
            domain_name=self.domain_artifacts.domain_name,
            domains_root=settings.domains_root,
            vector_source_fields=self.domain_artifacts.search_config.vector_source_fields,
            lexical_template_length=len(self.domain_artifacts.templates.lexical_search),
            vector_template_length=len(self.domain_artifacts.templates.vector_search),
            graph_context_template_length=len(self.domain_artifacts.templates.graph_context_query),
            llm_answer_prompt_length=len(self.domain_artifacts.templates.llm_answer_prompt),
        )

        self.opensearch_adapter = OpenSearchAdapter(
            settings=settings, domain_artifacts=self.domain_artifacts
        )
        self.neo4j_adapter = Neo4jAdapter(settings=settings, domain_artifacts=self.domain_artifacts)
        self.embedding_service = EmbeddingService(settings=settings)
        self.llm_service = LLMService(settings=settings, domain_artifacts=self.domain_artifacts)
        self.search_service = SearchService(
            opensearch_adapter=self.opensearch_adapter,
            neo4j_adapter=self.neo4j_adapter,
            embedding_service=self.embedding_service,
            llm_service=self.llm_service,
            settings=settings,
            domain_artifacts=self.domain_artifacts,
        )

    async def warmup(self) -> None:
        """Warm up startup dependencies."""

        await self.embedding_service.preload_model()
        await self.llm_service.preload_model()

    async def close(self) -> None:
        """Close all adapters."""

        await self.opensearch_adapter.close()
        await self.neo4j_adapter.close()
        await self.embedding_service.close()
        await self.llm_service.close()


def _resolve_search_service(request: Request) -> SearchService:
    """Resolve search service from application state."""

    return request.app.state.container.search_service


def _add_middlewares(app: FastAPI, settings: Settings) -> None:
    """Register middleware stack."""

    @app.middleware("http")
    async def request_id_http_middleware(request: Request, call_next: RequestResponseEndpoint):
        """Bind request id for each incoming request."""

        return await request_id_middleware(request=request, call_next=call_next, settings=settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""

    settings = get_settings()
    configure_logging(log_level=settings.app_log_level)
    app.state.container = AppContainer(settings=settings)
    await app.state.container.warmup()
    yield
    await app.state.container.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    _add_middlewares(app=app, settings=settings)

    app.dependency_overrides[get_search_service] = _resolve_search_service
    app.include_router(router, prefix=settings.api_v1_prefix)
    app.include_router(frontend_router)
    app.mount("/ui/static", StaticFiles(directory=STATIC_DIR), name="ui-static")
    return app


app = create_app()
