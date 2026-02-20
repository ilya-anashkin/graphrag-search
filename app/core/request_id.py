"""Request ID middleware."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from app.core.config import Settings
from app.core.logging import request_id_context

RequestHandler = Callable[[Request], Awaitable[Response]]


def _resolve_request_id(request: Request, request_id_header: str) -> str:
    """Extract request id from header or create new one."""

    existing_request_id = request.headers.get(request_id_header)
    if existing_request_id:
        return existing_request_id
    return str(uuid4())


async def request_id_middleware(request: Request, call_next: RequestHandler, settings: Settings) -> Response:
    """Set request id context and propagate it in response headers."""

    request_id = _resolve_request_id(request, settings.request_id_header)
    token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
        response.headers[settings.request_id_header] = request_id
        return response
    finally:
        request_id_context.reset(token)
