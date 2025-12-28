from __future__ import annotations

import logging

from neo4j import GraphDatabase

from ..logging_config import configure_logging
from ..services import GraphService
from ..settings import get_settings


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    driver = GraphDatabase.driver(settings.neo4j_uri, auth=settings.neo4j_auth())
    service = GraphService(driver, settings)
    logger.info("Initializing Neo4j schema and constraints.")
    service.ensure_constraints()
    logger.info("Neo4j initialization completed.")
    driver.close()


if __name__ == "__main__":
    main()
