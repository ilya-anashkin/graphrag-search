"""Domain configuration and template loader."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DomainSearchConfig:
    """Search-specific domain settings."""

    vector_source_fields: list[str]
    graph_node_label_movie: str
    graph_node_label_actor: str
    graph_node_label_director: str
    graph_node_label_screenwriter: str
    graph_node_label_country: str
    graph_rel_acted_in: str
    graph_rel_directed: str
    graph_rel_wrote: str
    graph_rel_produced_in: str
    llm_domain_schema: dict[str, Any]


@dataclass(slots=True)
class DomainTemplates:
    """Mustache templates for domain search queries."""

    lexical_search: str
    vector_search: str
    graph_context_query: str
    llm_answer_prompt: str


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
        graph_context_query_path = domain_path / "templates" / "graph_context.cypher.mustache"
        llm_answer_prompt_path = domain_path / "templates" / "llm_answer_prompt.mustache"

        config_payload = self._load_json(path=config_path)
        index_body = config_payload.get("index", {})
        search_payload = config_payload.get("search", {})
        graph_payload = search_payload.get("graph", {})
        llm_payload = search_payload.get("llm", {})

        return DomainArtifacts(
            domain_name=self._domain_name,
            index_body=index_body,
            search_config=DomainSearchConfig(
                vector_source_fields=[str(item) for item in search_payload.get("vector_source_fields", [])],
                graph_node_label_movie=str(graph_payload.get("movie_label", "Movie")),
                graph_node_label_actor=str(graph_payload.get("actor_label", "Actor")),
                graph_node_label_director=str(graph_payload.get("director_label", "Director")),
                graph_node_label_screenwriter=str(graph_payload.get("screenwriter_label", "Screenwriter")),
                graph_node_label_country=str(graph_payload.get("country_label", "Country")),
                graph_rel_acted_in=str(graph_payload.get("acted_in_rel", "ACTED_IN")),
                graph_rel_directed=str(graph_payload.get("directed_rel", "DIRECTED")),
                graph_rel_wrote=str(graph_payload.get("wrote_rel", "WROTE")),
                graph_rel_produced_in=str(graph_payload.get("produced_in_rel", "PRODUCED_IN")),
                llm_domain_schema=dict(llm_payload.get("domain_schema", {})),
            ),
            templates=DomainTemplates(
                lexical_search=self._load_text(path=lexical_template_path),
                vector_search=self._load_text(path=vector_template_path),
                graph_context_query=self._load_text(path=graph_context_query_path),
                llm_answer_prompt=self._load_text(path=llm_answer_prompt_path),
            ),
        )

    def _load_json(self, path: Path) -> dict[str, Any]:
        """Load and parse JSON file."""

        return json.loads(path.read_text(encoding="utf-8"))

    def _load_text(self, path: Path) -> str:
        """Load UTF-8 text file."""

        return path.read_text(encoding="utf-8")
