"""Load domain JSONL into Neo4j as graph relations."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.adapters.neo4j_client import Neo4jAdapter
from app.core.config import get_settings
from app.core.domain_loader import DomainLoader


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Ingest domain JSONL into Neo4j graph")
    parser.add_argument("--file", default=None, help="Path to JSONL input file")
    parser.add_argument(
        "--batch-size", type=int, default=None, help="Neo4j ingest batch size."
    )
    return parser.parse_args()


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from JSONL file."""

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            content = line.strip()
            if not content:
                continue
            yield json.loads(content)


def normalize_id(raw_id: Any, domain_name: str) -> str:
    """Normalize source id to service document id format."""

    value = str(raw_id).strip()
    if "-" in value:
        return value
    return f"{domain_name}-{value}"


def resolve_default_dataset_path() -> Path:
    """Resolve default dataset path from active domain."""

    settings = get_settings()
    domain_dir = Path(settings.domains_root) / settings.domain_name
    example_data_dir = domain_dir / "example_data"
    if example_data_dir.exists():
        candidates = sorted(example_data_dir.glob("*.jsonl"))
        if candidates:
            return candidates[0]

    data_dir = domain_dir / "data"
    if data_dir.exists():
        candidates = sorted(data_dir.glob("*.jsonl"))
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        f"Default dataset for domain '{settings.domain_name}' not found. "
        "Provide --file explicitly or add *.jsonl to example_data/ or data/."
    )


def chunk_rows(
    rows: list[dict[str, Any]], batch_size: int
) -> list[list[dict[str, Any]]]:
    """Split rows into fixed-size batches."""

    return [
        rows[index : index + batch_size] for index in range(0, len(rows), batch_size)
    ]


async def ingest_graph(file_path: str, batch_size: int | None) -> None:
    """Execute graph ingestion workflow."""

    settings = get_settings()
    resolved_batch_size = batch_size or settings.graph_ingest_batch_size
    domain_loader = DomainLoader(
        domain_root=settings.domains_root, domain_name=settings.domain_name
    )
    domain_artifacts = domain_loader.load()
    neo4j_adapter = Neo4jAdapter(settings=settings, domain_artifacts=domain_artifacts)

    source_path = Path(file_path)
    if not source_path.exists():
        raise FileNotFoundError(f"JSONL file not found: {source_path}")

    rows: list[dict[str, Any]] = []
    for raw_row in iter_jsonl(source_path):
        raw_id = raw_row.get("id")
        if raw_id in (None, ""):
            continue
        rows.append(
            {
                "id": normalize_id(raw_id, domain_name=settings.domain_name),
                "movie": raw_row.get("movie", ""),
                "overview": raw_row.get("overview", ""),
                "year": raw_row.get("year"),
                "rating": raw_row.get("rating"),
                "rating_ball": raw_row.get("rating_ball"),
                "url_logo": raw_row.get("url_logo", ""),
                "country": raw_row.get("country"),
                "director": raw_row.get("director"),
                "screenwriter": raw_row.get("screenwriter"),
                "actors": raw_row.get("actors"),
            }
        )

    total = len(rows)
    ingested = 0
    batches = chunk_rows(rows=rows, batch_size=resolved_batch_size)
    progress_bar = (
        tqdm(total=len(batches), desc="Neo4j graph ingest", unit="batch")
        if tqdm
        else None
    )

    for batch in batches:
        batch_succeeded, _batch_failed = await neo4j_adapter.ingest_documents(
            rows=batch
        )
        ingested += len(batch_succeeded)
        if progress_bar is not None:
            progress_bar.update(1)

    if progress_bar is not None:
        progress_bar.close()

    await neo4j_adapter.close()
    print(
        f"Graph ingestion done. total={total} ingested={ingested} batch_size={resolved_batch_size}"
    )


def main() -> None:
    """CLI entrypoint."""

    args = parse_args()
    source_path = args.file or str(resolve_default_dataset_path())
    asyncio.run(ingest_graph(file_path=source_path, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
