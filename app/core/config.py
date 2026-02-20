"""Configuration module based on environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="graphrag-search-api", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")

    request_id_header: str = Field(default="X-Request-ID", alias="REQUEST_ID_HEADER")
    api_v1_prefix: str = Field(default="/v1", alias="API_V1_PREFIX")
    domain_name: str = Field(default="movies", alias="DOMAIN_NAME")
    domains_root: str = Field(default="app/domains", alias="DOMAINS_ROOT")

    api_timeout_seconds: float = Field(default=5.0, alias="API_TIMEOUT_SECONDS")
    retry_attempts: int = Field(default=3, alias="RETRY_ATTEMPTS")
    retry_wait_seconds: float = Field(default=0.5, alias="RETRY_WAIT_SECONDS")

    opensearch_base_url: str = Field(default="http://localhost:9200", alias="OPENSEARCH_BASE_URL")
    opensearch_index: str = Field(default="documents", alias="OPENSEARCH_INDEX")
    opensearch_title_field: str = Field(default="title", alias="OPENSEARCH_TITLE_FIELD")
    opensearch_content_field: str = Field(default="content", alias="OPENSEARCH_CONTENT_FIELD")
    opensearch_metadata_field: str = Field(default="metadata", alias="OPENSEARCH_METADATA_FIELD")
    opensearch_vector_field: str = Field(default="embedding", alias="OPENSEARCH_VECTOR_FIELD")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    embedding_normalize: bool = Field(default=True, alias="EMBEDDING_NORMALIZE")
    embedding_preload_on_startup: bool = Field(default=True, alias="EMBEDDING_PRELOAD_ON_STARTUP")

    lexical_search_weight: float = Field(default=0.6, alias="LEXICAL_SEARCH_WEIGHT")
    vector_search_weight: float = Field(default=0.4, alias="VECTOR_SEARCH_WEIGHT")
    lexical_candidate_size: int = Field(default=40, alias="LEXICAL_CANDIDATE_SIZE")
    vector_candidate_size: int = Field(default=60, alias="VECTOR_CANDIDATE_SIZE")
    bulk_index_batch_size: int = Field(default=100, alias="BULK_INDEX_BATCH_SIZE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
