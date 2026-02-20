"""Neo4j adapter for graph traversal."""

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed

from app.core.config import Settings
from app.core.logging import get_logger

GRAPH_QUERY = """
MATCH (n)
WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $search_query)
RETURN elementId(n) AS id, labels(n) AS labels
LIMIT $limit
"""


class Neo4jAdapter:
    """Neo4j adapter with retries and safe error handling."""

    def __init__(self, settings: Settings) -> None:
        """Initialize graph driver."""

        self._settings = settings
        self._logger = get_logger(__name__)
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def close(self) -> None:
        """Close Neo4j driver."""

        await self._driver.close()

    async def search_nodes(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Search nodes by matching query against any node property."""

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._settings.retry_attempts),
                wait=wait_fixed(self._settings.retry_wait_seconds),
                reraise=True,
            ):
                with attempt:
                    return await self._run_query(query=query, limit=limit)
        except Exception as error:
            self._logger.error("neo4j_search_failed", error=str(error), query=query)
            return []

    async def _run_query(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Execute node search query and map result rows."""

        async with self._driver.session(database=self._settings.neo4j_database) as session:
            query_parameters = {"search_query": query, "limit": limit}
            cursor = await session.run(GRAPH_QUERY, parameters=query_parameters)
            rows = await cursor.data()
            return [
                {
                    "source": "neo4j",
                    "id": str(row.get("id", "")),
                    "score": 1.0,
                    "payload": {"labels": ",".join(row.get("labels", []))},
                }
                for row in rows
            ]

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
