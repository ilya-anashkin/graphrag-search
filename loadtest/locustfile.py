"""Locust scenarios for GraphRAG API load testing."""

from __future__ import annotations

import os
import random

from locust import HttpUser, LoadTestShape, between, task

SEARCH_QUERIES = [
    "про робота в космосе",
    "про магию и волшебников",
    "с Харрисоном Фордом",
    "Кристофера Нолана",
    "про космос с Харрисоном Фордом",
    "похожие на Интерстеллар по создателям",
    "Похожие по актёрам Пятого Элемента",
    "Похожие по сценарию Валли",
    "что посмотреть после Темного рыцаря",
    "какие фильмы похожи на ВАЛЛ·И",
    "какие актеры снимались в фильмах про космос",
    "какие режиссеры есть среди фильмов про магию",
    "какие страны встречаются среди мультфильмов",
    "про космос с Леонардо ДиКаприо",
    "российские фильмы Кристофера Нолана",
    "про Бэтмена с Джимом Керри",
]

SEARCH_MODE = os.getenv("LOCUST_SEARCH_MODE", "lexical_vector_graph")
SEARCH_LIMIT = int(os.getenv("LOCUST_SEARCH_LIMIT", "8"))
SEARCH_TASK_WEIGHT = int(os.getenv("LOCUST_SEARCH_TASK_WEIGHT", "4"))
LOAD_SCENARIO = os.getenv("LOCUST_LOAD_SCENARIO", "step").strip().lower()


class GraphRAGUser(HttpUser):
    """User load profile for search traffic."""

    wait_time = between(0.2, 1.2)

    def _search_payload(self) -> dict[str, object]:
        return {
            "query": random.choice(SEARCH_QUERIES),
            "limit": SEARCH_LIMIT,
            "search_mode": SEARCH_MODE,
            "lexical_weight": 0.6,
            "vector_weight": 0.4,
        }

    @task(SEARCH_TASK_WEIGHT)
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
            except ValueError:
                response.failure("invalid_json")
                return

            if "items" not in body:
                response.failure("missing_items")
                return

            response.success()


class ScenarioShape(LoadTestShape):
    """Scenario-based load profiles for step, spike and soak testing."""

    step_stages = (
        {"duration": 120, "users": 20, "spawn_rate": 5},
        {"duration": 240, "users": 50, "spawn_rate": 10},
        {"duration": 360, "users": 100, "spawn_rate": 20},
        {"duration": 480, "users": 150, "spawn_rate": 20},
    )
    spike_stages = (
        {"duration": 60, "users": 20, "spawn_rate": 5},
        {"duration": 120, "users": 200, "spawn_rate": 100},
        {"duration": 180, "users": 20, "spawn_rate": 100},
    )
    soak_stages = (
        {"duration": 120, "users": 30, "spawn_rate": 10},
        {"duration": 1020, "users": 30, "spawn_rate": 10},
    )

    def tick(self):
        run_time = self.get_run_time()
        stages = self._resolve_stages()
        for stage in stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None

    def _resolve_stages(self) -> tuple[dict[str, int], ...]:
        if LOAD_SCENARIO == "spike":
            return self.spike_stages
        if LOAD_SCENARIO == "soak":
            return self.soak_stages
        return self.step_stages
