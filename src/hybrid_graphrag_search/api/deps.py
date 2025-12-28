from __future__ import annotations

import logging

from fastapi import Depends
from neo4j import GraphDatabase
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer

from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


def get_opensearch_client(settings: Settings) -> OpenSearch:
    logger.info("Creating OpenSearch client for %s", settings.opensearch_url())
    return OpenSearch(hosts=[settings.opensearch_url()], **settings.opensearch_auth())


def get_graph_driver(settings: Settings):
    logger.info("Creating Neo4j driver for %s", settings.neo4j_uri)
    return GraphDatabase.driver(settings.neo4j_uri, auth=settings.neo4j_auth())


def get_embedding_model(settings: Settings):
    logger.info("Loading embedding model %s", settings.embedding_model_name)
    return SentenceTransformer(settings.embedding_model_name)


def opensearch_dep(settings: Settings = Depends(get_settings)) -> OpenSearch:
    return get_opensearch_client(settings)


def graph_driver_dep(settings: Settings = Depends(get_settings)):
    return get_graph_driver(settings)


def embedding_model_dep(settings: Settings = Depends(get_settings)):
    return get_embedding_model(settings)
