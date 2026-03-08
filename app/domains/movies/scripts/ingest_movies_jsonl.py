"""Bulk ingest domain JSONL dataset into the API service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_BULK_ENDPOINT = "/v1/documents/bulk"
DEFAULT_BATCH_SIZE = 25


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Ingest domain JSONL into API in bulk mode"
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
    return parser.parse_args()


def _normalize_value(value: Any) -> Any:
    """Normalize JSONL field value for target document."""

    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


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


def build_document_payload(
    raw_item: dict[str, Any], domain_name: str
) -> dict[str, Any]:
    """Map source JSONL record to API bulk document payload."""

    source_id = str(raw_item.get("id", "")).strip()
    if not source_id:
        raise ValueError("Missing id field")

    document: dict[str, Any] = {}
    for key, value in raw_item.items():
        if key == "id":
            continue
        document[key] = value

    if "-" in source_id:
        normalized_id = source_id
    else:
        normalized_id = f"{domain_name}-{source_id}"

    return {"id": normalized_id, "document": document}


def load_payloads(path: Path, domain_name: str) -> list[dict[str, Any]]:
    """Read JSONL file and convert rows into API payloads."""

    payloads: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                item = json.loads(stripped)
                payloads.append(
                    build_document_payload(raw_item=item, domain_name=domain_name)
                )
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(
                    f"Invalid JSONL line {line_number}: {error}"
                ) from error

    return payloads


def chunk_items(
    items: list[dict[str, Any]], batch_size: int
) -> list[list[dict[str, Any]]]:
    """Split payload list into batches."""

    return [
        items[index : index + batch_size] for index in range(0, len(items), batch_size)
    ]


async def send_bulk_batches(
    client: httpx.AsyncClient,
    endpoint: str,
    payloads: list[dict[str, Any]],
    batch_size: int,
) -> tuple[int, int, list[str]]:
    """Send bulk requests and return aggregate stats."""

    total_indexed = 0
    total_failed = 0
    failed_ids: list[str] = []
    batches = chunk_items(items=payloads, batch_size=batch_size)
    progress_bar = (
        tqdm(total=len(batches), desc="OpenSearch bulk ingest", unit="batch")
        if tqdm
        else None
    )

    for batch in batches:
        request_payload = {"items": batch}
        response = await client.post(endpoint, json=request_payload)
        response.raise_for_status()

        body = response.json()
        total_indexed += int(body.get("indexed", 0))
        total_failed += int(body.get("failed", 0))
        failed_ids.extend([str(item) for item in body.get("failed_ids", [])])
        if progress_bar is not None:
            progress_bar.update(1)

    if progress_bar is not None:
        progress_bar.close()

    return total_indexed, total_failed, failed_ids


async def main() -> None:
    """CLI entrypoint."""

    args = parse_args()
    settings = get_settings()
    dataset_path = Path(args.file) if args.file else resolve_default_dataset_path()

    payloads = load_payloads(path=dataset_path, domain_name=settings.domain_name)
    if not payloads:
        print("No records found in input file")
        return

    async with httpx.AsyncClient(
        base_url=args.api_base_url, timeout=args.timeout
    ) as client:
        indexed, failed, failed_ids = await send_bulk_batches(
            client=client,
            endpoint=args.bulk_endpoint,
            payloads=payloads,
            batch_size=args.batch_size,
        )

    print(f"Total records: {len(payloads)}")
    print(f"Indexed: {indexed}")
    print(f"Failed: {failed}")
    if failed_ids:
        print(f"Failed IDs: {', '.join(failed_ids)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
