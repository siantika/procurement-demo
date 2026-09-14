"""Project-level HTTP middleware."""

import logging
import re
import time
import uuid

from .metrics import observe_request

CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}\Z")


class CorrelationIdMiddleware:
    """Teruskan correlation ID yang aman atau buat UUID baru."""

    header_name = "X-Correlation-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied_id = request.headers.get(self.header_name, "")
        if CORRELATION_ID_PATTERN.fullmatch(supplied_id):
            correlation_id = supplied_id
        else:
            correlation_id = str(uuid.uuid4())

        request.correlation_id = correlation_id
        response = self.get_response(request)
        response[self.header_name] = correlation_id
        return response


logger = logging.getLogger("procurement.http")


def _request_outcome(status_code):
    if status_code in {401, 403}:
        return "denied"
    if status_code >= 500:
        return "error"
    if status_code >= 400:
        return "client_error"
    return "success"


class RequestObservabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - started
        match = getattr(request, "resolver_match", None)
        route = match.view_name if match and match.view_name else "unknown"
        observe_request(
            method=request.method,
            route=route,
            status_code=response.status_code,
            duration_seconds=duration,
        )
        logger.info(
            "HTTP request completed",
            extra={
                "correlation_id": getattr(
                    request, "correlation_id", None
                ),
                "operation": "http_request",
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 3),
                "outcome": _request_outcome(response.status_code),
            },
        )
        return response
