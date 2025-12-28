from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from opensearchpy import OpenSearch

from .api import deps
from .services import GraphService, OpenSearchIndexService
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class EvalSample:
    query: str
    relevant_chunk_ids: List[str]
    relevant_doc_ids: List[str]


def load_dataset(path: Path) -> List[EvalSample]:
    samples: List[EvalSample] = []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            samples.append(
                EvalSample(
                    query=obj["query"],
                    relevant_chunk_ids=obj.get("relevant_chunk_ids", []),
                    relevant_doc_ids=obj.get("relevant_doc_ids", []),
                )
            )
    logger.info("Loaded %d eval samples", len(samples))
    return samples


def recall_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = len(set(relevant) & set(retrieved[:k]))
    return hits / len(relevant)


def mrr_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> float:
    for idx, rid in enumerate(retrieved[:k]):
        if rid in relevant:
            return 1.0 / (idx + 1)
    return 0.0


def ndcg_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> float:
    import math

    dcg = 0.0
    for idx, rid in enumerate(retrieved[:k]):
        if rid in relevant:
            dcg += 1.0 / math.log2(idx + 2)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def _extract_ids(hits: Iterable[dict]) -> List[str]:
    ids: List[str] = []
    for h in hits:
        if isinstance(h, dict):
            if "_id" in h:
                ids.append(h["_id"])
            elif "doc_id" in h:
                ids.append(h["doc_id"])
            elif "chunk_id" in h:
                ids.append(h["chunk_id"])
    return ids


def eval_config(
    samples: List[EvalSample],
    retrieve_fn,
    k: int,
) -> dict[str, float]:
    recalls: List[float] = []
    mrrs: List[float] = []
    ndcgs: List[float] = []
    for sample in samples:
        hits = retrieve_fn(sample.query, k)
        retrieved_ids = _extract_ids(hits)
        relevant = sample.relevant_chunk_ids or sample.relevant_doc_ids
        recalls.append(recall_at_k(relevant, retrieved_ids, k))
        mrrs.append(mrr_at_k(relevant, retrieved_ids, k))
        ndcgs.append(ndcg_at_k(relevant, retrieved_ids, k))
    return {
        "recall@k": sum(recalls) / len(recalls) if recalls else 0.0,
        "mrr@k": sum(mrrs) / len(mrrs) if mrrs else 0.0,
        "ndcg@k": sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
    }


def run_evaluation(dataset_path: Path, k: int, settings: Optional[Settings] = None) -> dict:
    settings = settings or get_settings()
    samples = load_dataset(dataset_path)

    os_client: OpenSearch = deps.get_opensearch_client(settings)
    os_service = OpenSearchIndexService(os_client, settings)

    # Graph driver is optional for evaluation mode D
    try:
        graph_driver = deps.get_graph_driver(settings)
        graph_service = GraphService(graph_driver, settings)
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.warning("Graph driver init failed: %s", exc)
        graph_service = None

    def bm25_only(query: str, top_k: int):
        try:
            return os_service.search_bm25(query, top_k)
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.error("BM25 search failed: %s", exc)
            return []

    def dense_only(query: str, top_k: int):
        logger.warning("Dense-only search not implemented; returning empty.")
        return []

    def hybrid_no_graph(query: str, top_k: int):
        try:
            bm25_hits = os_service.search_bm25(query, top_k)
            dense_hits = dense_only(query, top_k)
            return bm25_hits[: top_k // 2] + dense_hits[: top_k // 2]
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.error("Hybrid search failed: %s", exc)
            return []

    def hybrid_with_graph(query: str, top_k: int):
        base = hybrid_no_graph(query, top_k)
        if not graph_service:
            return base
        try:
            seed_ids = _extract_ids(base)
            neighbors = graph_service.expand_neighbors(seed_ids, hops=1, limit_per_seed=5)
            neighbor_hits = [
                {"_id": n["neighbor_chunk_id"], "_via": n.get("via_edges")} for n in neighbors
            ]
            return base + neighbor_hits
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.error("Graph expansion failed: %s", exc)
            return base

    configs = {
        "bm25": bm25_only,
        "dense": dense_only,
        "hybrid": hybrid_no_graph,
        "hybrid_graph": hybrid_with_graph,
    }

    results = {}
    for name, fn in configs.items():
        logger.info("Evaluating config %s", name)
        results[name] = eval_config(samples, fn, k)
    return results


def print_table(results: dict, k: int) -> None:
    print(f"{'Config':<15} {'Recall@'+str(k):<12} {'MRR@'+str(k):<12} {'nDCG@'+str(k):<12}")
    for name, metrics in results.items():
        print(
            f"{name:<15} "
            f"{metrics['recall@k']:.4f}    "
            f"{metrics['mrr@k']:.4f}    "
            f"{metrics['ndcg@k']:.4f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate hybrid-graphrag-search retrieval.")
    parser.add_argument("--dataset", type=Path, required=True, help="Path to eval JSONL file")
    parser.add_argument("--k", type=int, default=10, help="Cutoff for metrics")
    parser.add_argument("--out", type=Path, default=None, help="Write results JSON")
    args = parser.parse_args()

    settings = get_settings()
    logger_level = settings.log_level
    logging.basicConfig(level=logger_level, format="%(asctime)s | %(levelname)s | %(message)s")

    results = run_evaluation(args.dataset, args.k, settings=settings)
    print_table(results, args.k)

    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        logger.info("Wrote results to %s", args.out)


if __name__ == "__main__":
    main()
