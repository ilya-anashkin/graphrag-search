"""LLM service tests."""

from app.core.config import Settings
from app.core.domain_loader import DomainArtifacts, DomainSearchConfig, DomainTemplates
from app.services.llm_service import LLMService


def build_domain_artifacts() -> DomainArtifacts:
    """Build fake domain artifacts for LLM tests."""

    return DomainArtifacts(
        domain_name="movies",
        index_body={},
        search_config=DomainSearchConfig(
            vector_source_fields=["movie", "overview"],
            graph_node_label_movie="Movie",
            graph_node_label_actor="Actor",
            graph_node_label_director="Director",
            graph_node_label_screenwriter="Screenwriter",
            graph_node_label_country="Country",
            graph_rel_acted_in="ACTED_IN",
            graph_rel_directed="DIRECTED",
            graph_rel_wrote="WROTE",
            graph_rel_produced_in="PRODUCED_IN",
            llm_domain_schema={"entity": "MovieSearchResult"},
        ),
        templates=DomainTemplates(
            lexical_search="{}",
            vector_search="{}",
            graph_context_query="MATCH (n) RETURN n",
            llm_answer_prompt="{{question}}\n{{context}}\n{{data_schema}}\n{{allowed_ids}}",
        ),
    )


def test_postprocess_answer_strips_think_and_validates_sources() -> None:
    """LLM postprocess should separate think block and keep plain answer."""

    service = LLMService(
        settings=Settings(),
        domain_artifacts=build_domain_artifacts(),
    )
    raw = '<think>hidden</think>{"answer":"Рекомендую Интерстеллар [movie-1]","source_ids":["movie-1","movie-x"]}'
    result = service._postprocess_answer(raw_answer=raw)  # noqa: SLF001
    assert result["think"] == "hidden"
    assert result["answer"] == "Рекомендую Интерстеллар [movie-1]"


def test_postprocess_answer_without_valid_source_returns_plain_answer() -> None:
    """LLM postprocess should keep plain answer from JSON payload."""

    service = LLMService(
        settings=Settings(),
        domain_artifacts=build_domain_artifacts(),
    )
    raw = '{"answer":"Нерелевантный ответ","source_ids":["movie-x"]}'
    result = service._postprocess_answer(  # noqa: SLF001
        raw_answer=raw
    )
    assert result["answer"] == "Нерелевантный ответ"
    assert result["think"] is None
