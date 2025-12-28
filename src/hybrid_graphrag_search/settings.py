from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field("hybrid-graphrag-search", validation_alias="APP_NAME")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")

    opensearch_host: str = Field("localhost", validation_alias="OPENSEARCH_HOST")
    opensearch_port: int = Field(9200, validation_alias="OPENSEARCH_PORT")
    opensearch_username: str = Field("admin", validation_alias="OPENSEARCH_USERNAME")
    opensearch_password: str = Field("admin", validation_alias="OPENSEARCH_PASSWORD")
    opensearch_index: str = Field("documents", validation_alias="OPENSEARCH_INDEX")

    neo4j_uri: str = Field("bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field("password", validation_alias="NEO4J_PASSWORD")

    embedding_model_name: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", validation_alias="EMBEDDING_MODEL_NAME"
    )
    embedding_dimension: int = Field(384, validation_alias="EMBEDDING_DIMENSION")
    chunk_size: int = Field(500, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(50, validation_alias="CHUNK_OVERLAP")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def opensearch_url(self) -> str:
        return f"http://{self.opensearch_host}:{self.opensearch_port}"

    def opensearch_auth(self) -> Dict[str, Any]:
        return {
            "http_auth": (self.opensearch_username, self.opensearch_password),
        }

    def neo4j_auth(self) -> tuple[str, str]:
        return (self.neo4j_user, self.neo4j_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
