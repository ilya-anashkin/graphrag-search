"""Bulk ingest expanded domain JSONL dataset into the API service."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.domains.movies.scripts.ingest_movies_jsonl import (
    DEFAULT_API_BASE_URL,
    DEFAULT_BATCH_SIZE,
    DEFAULT_BULK_ENDPOINT,
    load_payloads,
    resolve_default_dataset_path,
    send_bulk_batches,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Ingest expanded domain JSONL into API in bulk mode"
    )
    parser.add_argument("--file", default=None, help="Path to JSONL input file")
    parser.add_argument(
        "--api-base-url", default=DEFAULT_API_BASE_URL, help="API base URL"
    )
    parser.add_argument(
        "--bulk-endpoint",
        default=DEFAULT_BULK_ENDPOINT,
        help="Bulk indexing endpoint path",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Bulk batch size"
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="HTTP request timeout in seconds"
    )
    parser.add_argument(
        "--multiplier",
        type=int,
        default=10,
        help="How many replicated copies of the source dataset to generate",
    )
    return parser.parse_args()


def expand_payloads(
    payloads: list[dict[str, Any]],
    multiplier: int,
) -> list[dict[str, Any]]:
    """Duplicate payloads with unique identifiers for load testing."""

    expanded: list[dict[str, Any]] = []
    for replica_index in range(1, multiplier + 1):
        for item in payloads:
            base_id = str(item["id"])
            expanded.append(
                {
                    "id": f"{base_id}-rep-{replica_index:03d}",
                    "document": dict(item["document"]),
                }
            )
    return expanded


async def main() -> None:
    """CLI entrypoint."""

    args = parse_args()
    if args.multiplier <= 0:
        raise ValueError("--multiplier must be greater than 0")

    settings = get_settings()
    dataset_path = Path(args.file) if args.file else resolve_default_dataset_path()
    source_payloads = load_payloads(path=dataset_path, domain_name=settings.domain_name)
    if not source_payloads:
        print("No records found in input file")
        return

    expanded_payloads = expand_payloads(
        payloads=source_payloads,
        multiplier=args.multiplier,
    )

    async with httpx.AsyncClient(
        base_url=args.api_base_url, timeout=args.timeout
    ) as client:
        indexed, failed, failed_ids = await send_bulk_batches(
            client=client,
            endpoint=args.bulk_endpoint,
            payloads=expanded_payloads,
            batch_size=args.batch_size,
        )

    print(f"Source records: {len(source_payloads)}")
    print(f"Multiplier: {args.multiplier}")
    print(f"Expanded records: {len(expanded_payloads)}")
    print(f"Indexed: {indexed}")
    print(f"Failed: {failed}")
    if failed_ids:
        print(f"Failed IDs: {', '.join(failed_ids)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
