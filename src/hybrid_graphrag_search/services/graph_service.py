from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neo4j import Driver

from ..settings import Settings

logger = logging.getLogger(__name__)


class GraphService:
    """Service handling graph writes and expansions in Neo4j."""

    def __init__(self, driver: Optional[Driver], settings: Settings) -> None:
        self.driver = driver
        self.settings = settings
        logger.debug("Initialized GraphService with Neo4j URI %s", self.settings.neo4j_uri)

    def ensure_constraints(self) -> None:
        session = self._require_session()
        logger.info("Ensuring Neo4j constraints and indexes for Chunk nodes.")
        with session as s:
            s.execute_write(
                lambda tx: tx.run(
                    "CREATE CONSTRAINT chunk_id IF NOT EXISTS "
                    "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE"
                )
            )
            s.execute_write(
                lambda tx: tx.run(
                    "CREATE INDEX chunk_doc_id IF NOT EXISTS FOR (c:Chunk) ON (c.doc_id)"
                )
            )

    def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            logger.warning("No chunks provided for upsert.")
            return
        session = self._require_session()
        logger.info("Upserting %d chunks into Neo4j.", len(chunks))
        with session as s:
            s.execute_write(
                lambda tx: tx.run(
                    """
                    UNWIND $rows AS row
                    MERGE (c:Chunk {chunk_id: row.chunk_id})
                      SET c.doc_id = row.doc_id,
                          c.title = row.title
                    """,
                    rows=chunks,
                )
            )

    def link_next_edges(self, doc_id: str, ordered_chunk_ids: List[str]) -> None:
        if len(ordered_chunk_ids) < 2:
            logger.info("Not linking NEXT edges: fewer than 2 chunks.")
            return
        session = self._require_session()
        logger.info("Linking NEXT edges for doc_id=%s", doc_id)
        pairs = [
            {"from_id": ordered_chunk_ids[i], "to_id": ordered_chunk_ids[i + 1]}
            for i in range(len(ordered_chunk_ids) - 1)
        ]
        with session as s:
            s.execute_write(
                lambda tx: tx.run(
                    """
                    UNWIND $pairs AS pair
                    MATCH (a:Chunk {chunk_id: pair.from_id, doc_id: $doc_id})
                    MATCH (b:Chunk {chunk_id: pair.to_id, doc_id: $doc_id})
                    MERGE (a)-[:NEXT]->(b)
                    """,
                    pairs=pairs,
                    doc_id=doc_id,
                )
            )

    def expand_neighbors(
        self, seed_chunk_ids: List[str], hops: int = 1, limit_per_seed: int = 10
    ) -> List[Dict[str, Any]]:
        if not seed_chunk_ids:
            return []
        session = self._require_session()
        logger.info(
            "Expanding neighbors for %d seed chunks with hops=%d limit=%d",
            len(seed_chunk_ids),
            hops,
            limit_per_seed,
        )
        with session as s:
            result = s.execute_read(
                lambda tx: tx.run(
                    """
                    UNWIND $seed_ids AS sid
                    CALL {
                        WITH sid
                        MATCH (s:Chunk {chunk_id: sid})
                        MATCH p=(s)-[r:NEXT|SIMILAR_TO|REFERS_TO*1..$hops]-(n:Chunk)
                        WHERE n.chunk_id <> sid
                        RETURN n.chunk_id AS neighbor_chunk_id,
                               n.doc_id AS neighbor_doc_id,
                               [rel IN relationships(p) | type(rel)] AS via_edges
                        LIMIT $limit_per_seed
                    }
                    RETURN sid AS seed_id, neighbor_chunk_id, neighbor_doc_id, via_edges
                    """,
                    seed_ids=seed_chunk_ids,
                    hops=hops,
                    limit_per_seed=limit_per_seed,
                ).data()
            )
        return result

    def get_subgraph(
        self, seed_chunk_ids: List[str], hops: int = 1
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not seed_chunk_ids:
            return {"nodes": [], "edges": []}
        session = self._require_session()
        logger.info("Fetching subgraph for %d seeds with hops=%d", len(seed_chunk_ids), hops)
        with session as s:
            nodes_result = s.execute_read(
                lambda tx: tx.run(
                    """
                    UNWIND $seed_ids AS sid
                    MATCH (s:Chunk {chunk_id: sid})
                    MATCH p=(s)-[:NEXT|SIMILAR_TO|REFERS_TO*0..$hops]-(n:Chunk)
                    WITH DISTINCT n RETURN n.chunk_id AS chunk_id, n.doc_id AS doc_id, n.title AS title
                    """,
                    seed_ids=seed_chunk_ids,
                    hops=hops,
                ).data()
            )
            edges_result = s.execute_read(
                lambda tx: tx.run(
                    """
                    UNWIND $seed_ids AS sid
                    MATCH (s:Chunk {chunk_id: sid})
                    MATCH p=(s)-[r:NEXT|SIMILAR_TO|REFERS_TO*1..$hops]-(n:Chunk)
                    UNWIND relationships(p) AS rel
                    WITH DISTINCT rel, startNode(rel) AS a, endNode(rel) AS b
                    RETURN a.chunk_id AS source, b.chunk_id AS target, type(rel) AS type
                    """,
                    seed_ids=seed_chunk_ids,
                    hops=hops,
                ).data()
            )
        return {"nodes": nodes_result, "edges": edges_result}

    def _require_session(self):
        if not self.driver:
            raise RuntimeError("Neo4j driver is not configured.")
        return self.driver.session()
