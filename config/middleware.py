"""Project-level HTTP middleware."""

import re
import uuid

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
