from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from .api import deps
from .api.routes import router as api_router
from .logging_config import configure_logging
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)

    @app.get("/health")
    def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
        logger.debug("Health check requested")
        opensearch_status = False
        neo4j_status = False

        try:
            client = deps.get_opensearch_client(settings)
            opensearch_status = bool(client.ping())
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.warning("OpenSearch health failed: %s", exc)

        try:
            driver = deps.get_graph_driver(settings)
            driver.verify_connectivity()
            neo4j_status = True
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.warning("Neo4j health failed: %s", exc)

        healthy = opensearch_status and neo4j_status
        if not healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"opensearch": opensearch_status, "neo4j": neo4j_status},
            )
        return {
            "status": "ok",
            "app": settings.app_name,
            "opensearch": opensearch_status,
            "neo4j": neo4j_status,
        }

    app.include_router(api_router, prefix="/api")
    logger.info("Application created with settings: %s", settings.model_dump())
    return app


app = create_app()
