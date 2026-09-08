"""Request correlation ID middleware.

Generates (or propagates) a short request ID for every request, exposes it
as `request.id`, echoes it back as a response header, and makes it available
to the logging formatters via a ContextVar (see apps/core/logging.py) so log
lines and future audit entries can be tied back to the originating request.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

REQUEST_ID_HEADER = "X-Request-ID"

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_current_request_id() -> str:
    """Read the request ID of the request currently being processed, if any."""
    return _request_id_ctx.get()


class RequestIDMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex[:12]
        request.id = request_id

        token = _request_id_ctx.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            _request_id_ctx.reset(token)

        response[REQUEST_ID_HEADER] = request_id
        return response
