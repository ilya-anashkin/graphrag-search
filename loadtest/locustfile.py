"""Locust сценарий для нагрузочного тестирования GraphRAG API."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

from locust import HttpUser, between, task

SEARCH_QUERIES = [
    "про космос",
    "фильм с монстрами",
    "драма о любви",
    "фантастика про будущее",
    "фильм про детективов",
    "мультфильм для всей семьи",
]

BULK_DATASET_FILE = os.getenv(
    "LOCUST_BULK_DATASET_FILE",
    "/mnt/domain-data/kinopoisk-top250.jsonl",
)
BULK_BATCH_SIZE = int(os.getenv("LOCUST_BULK_BATCH_SIZE", "5"))
BULK_SAMPLES_LIMIT = int(os.getenv("LOCUST_BULK_SAMPLES_LIMIT", "100"))


class GraphRAGUser(HttpUser):
    """Пользовательский профиль нагрузки для поиска и bulk-индексации."""

    wait_time = between(0.2, 1.2)
    _bulk_items_cache: list[dict[str, Any]] = []
    _bulk_cache_loaded = False

    def _search_payload(self) -> dict[str, Any]:
        return {
            "query": random.choice(SEARCH_QUERIES),
            "limit": random.choice([5, 10]),
            "lexical_weight": 0.6,
            "vector_weight": 0.4,
        }

    @classmethod
    def _load_bulk_items_cache(cls) -> None:
        """Load and normalize dataset rows for /v1/documents/bulk load testing."""

        if cls._bulk_cache_loaded:
            return

        dataset_path = Path(BULK_DATASET_FILE)
        if not dataset_path.exists():
            cls._bulk_items_cache = []
            cls._bulk_cache_loaded = True
            return

        items: list[dict[str, Any]] = []
        with dataset_path.open("r", encoding="utf-8") as source:
            for index, line in enumerate(source):
                row_raw = line.strip()
                if not row_raw:
                    continue
                try:
                    row = json.loads(row_raw)
                except json.JSONDecodeError:
                    continue
                document = cls._normalize_document(row=row)
                document_id = cls._resolve_document_id(row=row, index=index)
                items.append({"id": document_id, "document": document})
                if len(items) >= BULK_SAMPLES_LIMIT:
                    break

        cls._bulk_items_cache = items
        cls._bulk_cache_loaded = True

    @staticmethod
    def _normalize_document(row: dict[str, Any]) -> dict[str, Any]:
        """Keep domain fields expected by /v1/documents/bulk."""

        fields = [
            "rating",
            "movie",
            "year",
            "country",
            "rating_ball",
            "overview",
            "director",
            "screenwriter",
            "actors",
            "url_logo",
        ]
        normalized = {
            field: row.get(field) for field in fields if row.get(field) is not None
        }
        return normalized

    @staticmethod
    def _resolve_document_id(row: dict[str, Any], index: int) -> str:
        """Resolve stable document id from row."""

        if row.get("id") is not None:
            return str(row["id"])
        rating = row.get("rating")
        if rating is not None:
            return f"movie-{rating}"
        return f"locust-movie-{index}"

    def on_start(self) -> None:
        """Load dataset once per worker before executing tasks."""

        self._load_bulk_items_cache()

    @task(4)
    def search(self) -> None:
        payload = self._search_payload()
        with self.client.post(
            "/v1/search", json=payload, name="POST /v1/search", catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
                return

            try:
                body = response.json()
                if "items" not in body:
                    response.failure("missing_items")
                    return
            except json.JSONDecodeError:
                response.failure("invalid_json")
                return

            response.success()

    # @task(2)
    # def index_documents_bulk(self) -> None:
    #     """Load test for bulk indexing endpoint."""

    #     if not self._bulk_items_cache:
    #         return

    #     batch_size = max(1, BULK_BATCH_SIZE)
    #     if len(self._bulk_items_cache) <= batch_size:
    #         batch = list(self._bulk_items_cache)
    #     else:
    #         start = random.randint(0, len(self._bulk_items_cache) - batch_size)
    #         batch = self._bulk_items_cache[start : start + batch_size]

    #     payload = {"items": batch}
    #     with self.client.post(
    #         "/v1/documents/bulk",
    #         json=payload,
    #         name="POST /v1/documents/bulk",
    #         catch_response=True,
    #     ) as response:
    #         if response.status_code != 200:
    #             response.failure(f"status={response.status_code}")
    #             return
    #         response.success()
