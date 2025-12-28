from __future__ import annotations

import json
import os
from typing import List

import httpx

SAMPLE_DOCS = [
    {
        "doc_id": "doc-sample-1",
        "title": "GraphRAG Overview",
        "text": "Graph-based retrieval augments classic search by traversing graph neighbors.",
        "tags": ["demo", "graph"],
    },
    {
        "doc_id": "doc-sample-2",
        "title": "OpenSearch + Neo4j",
        "text": "OpenSearch handles BM25 and vector search while Neo4j stores chunk relationships.",
        "tags": ["demo", "stack"],
    },
]


def main() -> None:
    api_url = os.environ.get("API_URL", "http://localhost:8000/api/ingest")
    print(f"Ingesting {len(SAMPLE_DOCS)} docs to {api_url}")
    resp = httpx.post(api_url, json=SAMPLE_DOCS, timeout=30)
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()
