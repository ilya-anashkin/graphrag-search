from __future__ import annotations

import logging

from opensearchpy import OpenSearch

from ..logging_config import configure_logging
from ..services import OpenSearchIndexService
from ..settings import get_settings


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Initializing OpenSearch index: %s", settings.opensearch_index)
    client = OpenSearch(hosts=[settings.opensearch_url()], **settings.opensearch_auth())
    service = OpenSearchIndexService(client, settings)
    service.create_index_if_not_exists()
    logger.info("Index initialization completed.")


if __name__ == "__main__":
    main()
