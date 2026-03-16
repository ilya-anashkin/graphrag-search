"""Prometheus metrics for FastAPI runtime."""

from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI, Request
from starlette.responses import Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_CLIENT_AVAILABLE = True
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    PROMETHEUS_CLIENT_AVAILABLE = False

HTTP_REQUEST_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    15.0,
    20.0,
    30.0,
    45.0,
    60.0,
    90.0,
    120.0,
)

if PROMETHEUS_CLIENT_AVAILABLE:
    HTTP_REQUESTS_TOTAL = Counter(
        "graphrag_http_requests_total",
        "Total HTTP requests handled by FastAPI app.",
        ["method", "path", "status"],
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "graphrag_http_request_duration_seconds",
        "HTTP request duration in seconds.",
        ["method", "path"],
        buckets=HTTP_REQUEST_DURATION_BUCKETS,
    )
    HTTP_REQUESTS_IN_PROGRESS = Gauge(
        "graphrag_http_requests_in_progress",
        "Number of in-progress HTTP requests.",
        ["method", "path"],
    )
    HTTP_REQUEST_SIZE_BYTES = Counter(
        "graphrag_http_request_size_bytes_total",
        "Total HTTP request payload size in bytes.",
        ["method", "path"],
    )
    HTTP_RESPONSE_SIZE_BYTES = Counter(
        "graphrag_http_response_size_bytes_total",
        "Total HTTP response payload size in bytes.",
        ["method", "path", "status"],
    )


def _resolve_route_path(request: Request) -> str:
    """Resolve route path pattern for stable metrics labels."""

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return str(route_path) if route_path else request.url.path


def setup_metrics(app: FastAPI, metrics_path: str) -> None:
    """Attach Prometheus middleware and metrics endpoint to app."""

    if not PROMETHEUS_CLIENT_AVAILABLE:

        @app.get(metrics_path, include_in_schema=False)
        async def metrics_not_available() -> Response:
            """Expose installation hint when prometheus_client is missing."""

            return Response(
                content="prometheus_client is not installed",
                status_code=503,
                media_type="text/plain; charset=utf-8",
            )

        return

    @app.middleware("http")
    async def prometheus_metrics_middleware(request: Request, call_next):
        method = request.method
        path = _resolve_route_path(request=request)
        start = perf_counter()
        request_size_bytes = int(request.headers.get("content-length", "0") or 0)
        if request_size_bytes > 0:
            HTTP_REQUEST_SIZE_BYTES.labels(method=method, path=path).inc(
                request_size_bytes
            )
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            elapsed_seconds = perf_counter() - start
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(
                elapsed_seconds
            )
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=str(status_code),
            ).inc()
            response_size_bytes = int(response.headers.get("content-length", "0") or 0)
            if response_size_bytes > 0:
                HTTP_RESPONSE_SIZE_BYTES.labels(
                    method=method,
                    path=path,
                    status=str(status_code),
                ).inc(response_size_bytes)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()

        return response

    @app.get(metrics_path, include_in_schema=False)
    async def metrics() -> Response:
        """Expose Prometheus metrics."""

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
