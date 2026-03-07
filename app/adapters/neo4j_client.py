"""Neo4j adapter for graph traversal and graph context enrichment."""

from collections.abc import Iterable
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed

from app.core.config import Settings
from app.core.domain_loader import DomainArtifacts
from app.core.logging import get_logger

GRAPH_CONTEXT_LIMIT = 5


class Neo4jAdapter:
    """Neo4j adapter with retries and safe error handling."""

    def __init__(self, settings: Settings, domain_artifacts: DomainArtifacts) -> None:
        """Initialize graph driver."""

        self._settings = settings
        self._domain_artifacts = domain_artifacts
        self._logger = get_logger(__name__)
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._graph_context_query = self._render_graph_template(
            template=self._domain_artifacts.templates.graph_context_query
        )
        self._graph_ingest_query = self._render_graph_template(
            template=self._domain_artifacts.templates.graph_ingest_query
        )

    async def close(self) -> None:
        """Close Neo4j driver."""

        await self._driver.close()

    async def fetch_graph_context(
        self,
        item_ids: list[str],
        person_limit: int = GRAPH_CONTEXT_LIMIT,
        related_limit: int = 3,
        shared_people_limit: int = 5,
    ) -> dict[str, dict[str, Any]]:
        """Fetch graph context for indexed items by identifiers."""

        if not item_ids:
            return {}

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._settings.retry_attempts),
                wait=wait_fixed(self._settings.retry_wait_seconds),
                reraise=True,
            ):
                with attempt:
                    return await self._run_graph_context_query(
                        item_ids=item_ids,
                        person_limit=person_limit,
                        related_limit=related_limit,
                        shared_people_limit=shared_people_limit,
                    )
        except Exception as error:
            self._logger.error(
                "neo4j_context_query_failed", error=str(error), item_ids=item_ids[:20]
            )
            return {}

    async def _run_graph_context_query(
        self,
        item_ids: list[str],
        person_limit: int,
        related_limit: int,
        shared_people_limit: int,
    ) -> dict[str, dict[str, Any]]:
        """Execute domain graph context query and return map by item id."""

        async with self._driver.session(database=self._settings.neo4j_database) as session:
            query_parameters = {
                "item_ids": item_ids,
                "person_limit": person_limit,
                "related_limit": related_limit,
                "shared_people_limit": shared_people_limit,
            }
            cursor = await session.run(self._graph_context_query, parameters=query_parameters)
            rows = await cursor.data()
            self._logger.info(
                "neo4j_context_query_completed",
                requested_item_ids=len(item_ids),
                returned_rows=len(rows),
                person_limit=person_limit,
                related_limit=related_limit,
                shared_people_limit=shared_people_limit,
            )
            context_by_item_id: dict[str, dict[str, Any]] = {}
            for row in rows:
                item_id = str(row.get("item_id", ""))
                if not item_id:
                    continue
                directors = self._normalize_name_list(row.get("directors", []))
                screenwriters = self._normalize_name_list(row.get("screenwriters", []))
                actors = self._normalize_name_list(row.get("actors", []))
                countries = self._normalize_name_list(row.get("countries", []))
                context_by_item_id[item_id] = {
                    "connections": self._build_connections(
                        directors=directors,
                        screenwriters=screenwriters,
                        actors=actors,
                        countries=countries,
                    ),
                    "related_movies": self._normalize_related_movies(row.get("related_movies", [])),
                }
            return context_by_item_id

    async def ingest_documents(self, rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        """Insert domain documents into Neo4j as connected graph entities."""

        if not rows:
            return [], []

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._settings.retry_attempts),
                wait=wait_fixed(self._settings.retry_wait_seconds),
                reraise=True,
            ):
                with attempt:
                    return await self._run_ingest_query(rows=rows)
        except Exception as error:
            self._logger.error("neo4j_ingest_failed", error=str(error))
            failed_ids = [
                str(row.get("id", "")).strip() for row in rows if str(row.get("id", "")).strip()
            ]
            return [], failed_ids

    async def _run_ingest_query(self, rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        """Execute ingestion query with UNWIND batching payload."""

        normalized_rows = [self._normalize_ingest_row(row=row) for row in rows]
        async with self._driver.session(database=self._settings.neo4j_database) as session:
            cursor = await session.run(
                self._graph_ingest_query, parameters={"rows": normalized_rows}
            )
            await cursor.consume()
        succeeded_ids = [row["id"] for row in normalized_rows]
        return succeeded_ids, []

    def _normalize_ingest_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize one row for graph ingest query based on domain config."""

        config = self._domain_artifacts.search_config

        return {
            "id": str(row.get("id", "")),
            "title": str(row.get(config.graph_ingest_title_field, "")),
            "overview": str(row.get(config.graph_ingest_overview_field, "")),
            "year": self._to_int_or_none(row.get(config.graph_ingest_year_field)),
            "rating": self._to_int_or_none(row.get(config.graph_ingest_rating_field)),
            "rating_ball": self._to_float_or_none(row.get(config.graph_ingest_rating_ball_field)),
            "url_logo": str(row.get(config.graph_ingest_url_logo_field, "")),
            "countries": self._normalize_names(
                raw_value=row.get(config.graph_ingest_country_field)
            ),
            "directors": self._normalize_names(
                raw_value=row.get(config.graph_ingest_director_field)
            ),
            "screenwriters": self._normalize_names(
                raw_value=row.get(config.graph_ingest_screenwriter_field)
            ),
            "actors": self._normalize_names(raw_value=row.get(config.graph_ingest_actor_field)),
        }

    def _normalize_name_list(self, values: Any) -> list[str]:
        """Normalize raw query list payload to a list of strings."""

        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    def _normalize_related_movies(self, values: Any) -> list[dict[str, Any]]:
        """Normalize related movies payload from graph query."""

        if not isinstance(values, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            movie_id = str(item.get("id", "")).strip()
            movie_title = str(item.get("movie", "")).strip()
            if not movie_id:
                continue
            normalized.append(
                {
                    "id": movie_id,
                    "movie": movie_title,
                    "shared_people_count": self._to_int_or_none(item.get("shared_people_count"))
                    or 0,
                    "shared_people_relations": self._normalize_shared_people_relations(
                        item.get("shared_people_relations", [])
                    ),
                }
            )
        return normalized

    def _normalize_shared_people_relations(self, values: Any) -> list[dict[str, str]]:
        """Normalize shared people and relation types for related movies."""

        if not isinstance(values, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            person_name = str(item.get("person", "")).strip()
            source_relation = str(item.get("source_relation", "")).strip()
            related_relation = str(item.get("related_relation", "")).strip()
            if not person_name:
                continue
            normalized.append(
                {
                    "person": person_name,
                    "source_relation": source_relation,
                    "related_relation": related_relation,
                }
            )
        return normalized

    def _build_connections(
        self,
        directors: list[str],
        screenwriters: list[str],
        actors: list[str],
        countries: list[str],
    ) -> list[dict[str, str]]:
        """Build flat list of typed graph connections for one movie."""

        config = self._domain_artifacts.search_config
        connections: list[dict[str, str]] = []
        connections.extend(
            [
                {
                    "entity_type": config.graph_node_label_director,
                    "entity": name,
                    "relation": config.graph_rel_directed,
                }
                for name in directors
            ]
        )
        connections.extend(
            [
                {
                    "entity_type": config.graph_node_label_screenwriter,
                    "entity": name,
                    "relation": config.graph_rel_wrote,
                }
                for name in screenwriters
            ]
        )
        connections.extend(
            [
                {
                    "entity_type": config.graph_node_label_actor,
                    "entity": name,
                    "relation": config.graph_rel_acted_in,
                }
                for name in actors
            ]
        )
        connections.extend(
            [
                {
                    "entity_type": config.graph_node_label_country,
                    "entity": name,
                    "relation": config.graph_rel_produced_in,
                }
                for name in countries
            ]
        )
        return connections

    def _normalize_names(self, raw_value: Any) -> list[str]:
        """Convert scalar or list names to normalized list."""

        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            candidates: Iterable[Any] = raw_value
        else:
            candidates = str(raw_value).replace(";", ",").split(",")
        return [str(item).strip() for item in candidates if str(item).strip()]

    def _render_graph_template(self, template: str) -> str:
        """Render graph query template using domain graph labels and relation types."""

        config = self._domain_artifacts.search_config
        placeholders = {
            "movie_label": config.graph_node_label_movie,
            "actor_label": config.graph_node_label_actor,
            "director_label": config.graph_node_label_director,
            "screenwriter_label": config.graph_node_label_screenwriter,
            "country_label": config.graph_node_label_country,
            "acted_in_rel": config.graph_rel_acted_in,
            "directed_rel": config.graph_rel_directed,
            "wrote_rel": config.graph_rel_wrote,
            "produced_in_rel": config.graph_rel_produced_in,
        }
        rendered = template
        for key, value in placeholders.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered

    def _to_int_or_none(self, value: Any) -> int | None:
        """Convert value to int or return None."""

        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _to_float_or_none(self, value: Any) -> float | None:
        """Convert value to float or return None."""

        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def check_health(self) -> bool:
        """Return True when Neo4j can answer a trivial query."""

        try:
            async with self._driver.session(database=self._settings.neo4j_database) as session:
                cursor = await session.run("RETURN 1 AS ok")
                row = await cursor.single()
                return bool(row and row.get("ok") == 1)
        except Exception as error:
            self._logger.error("neo4j_health_failed", error=str(error))
            return False
