"""Domain configuration and template loader."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DomainSearchConfig:
    """Search-specific domain settings."""

    vector_source_fields: list[str]


@dataclass(slots=True)
class DomainTemplates:
    """Mustache templates for domain search queries."""

    lexical_search: str
    vector_search: str


@dataclass(slots=True)
class DomainArtifacts:
    """Loaded domain artifacts for indexing and search."""

    domain_name: str
    index_body: dict[str, Any]
    search_config: DomainSearchConfig
    templates: DomainTemplates


class DomainLoader:
    """Load domain artifacts from repository files."""

    def __init__(self, domain_root: str, domain_name: str) -> None:
        """Initialize loader with domain path settings."""

        self._domain_root = Path(domain_root)
        self._domain_name = domain_name

    def load(self) -> DomainArtifacts:
        """Load full domain artifacts package."""

        domain_path = self._domain_root / self._domain_name
        config_path = domain_path / "index_config.json"
        lexical_template_path = domain_path / "templates" / "lexical_search.mustache"
        vector_template_path = domain_path / "templates" / "vector_search.mustache"

        config_payload = self._load_json(path=config_path)
        index_body = config_payload.get("index", {})
        search_payload = config_payload.get("search", {})

        return DomainArtifacts(
            domain_name=self._domain_name,
            index_body=index_body,
            search_config=DomainSearchConfig(
                vector_source_fields=[str(item) for item in search_payload.get("vector_source_fields", [])],
            ),
            templates=DomainTemplates(
                lexical_search=self._load_text(path=lexical_template_path),
                vector_search=self._load_text(path=vector_template_path),
            ),
        )

    def _load_json(self, path: Path) -> dict[str, Any]:
        """Load and parse JSON file."""

        return json.loads(path.read_text(encoding="utf-8"))

    def _load_text(self, path: Path) -> str:
        """Load UTF-8 text file."""

        return path.read_text(encoding="utf-8")
