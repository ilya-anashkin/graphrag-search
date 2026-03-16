"""OpenTelemetry tracing setup."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

_TRACING_INITIALIZED = False


def setup_tracing(app: FastAPI, settings: Settings, logger: Any) -> None:
    """Configure tracing instrumentation and exporter."""

    global _TRACING_INITIALIZED

    if not settings.tracing_enabled:
        logger.info("tracing_disabled")
        return

    if _TRACING_INITIALIZED:
        return

    if not OTEL_AVAILABLE:
        logger.warning("tracing_not_available_missing_dependencies")
        return

    ratio = min(1.0, max(0.0, float(settings.tracing_sampling_ratio)))
    resource = Resource.create({"service.name": settings.tracing_service_name})
    tracer_provider = TracerProvider(
        resource=resource, sampler=TraceIdRatioBased(ratio)
    )
    span_exporter = OTLPSpanExporter(endpoint=settings.tracing_otlp_endpoint)
    span_processor = BatchSpanProcessor(span_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    FastAPIInstrumentor.instrument_app(app=app, tracer_provider=tracer_provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

    _TRACING_INITIALIZED = True
    logger.info(
        "tracing_initialized",
        endpoint=settings.tracing_otlp_endpoint,
        service_name=settings.tracing_service_name,
        sampling_ratio=ratio,
    )


def shutdown_tracing(logger: Any) -> None:
    """Flush and shutdown tracing provider."""

    if not OTEL_AVAILABLE:
        return

    tracer_provider = trace.get_tracer_provider()
    shutdown = getattr(tracer_provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
        logger.info("tracing_shutdown")
