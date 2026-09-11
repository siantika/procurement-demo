"""Tests untuk project middleware."""

import uuid

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.middleware import CorrelationIdMiddleware


class CorrelationIdMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CorrelationIdMiddleware(
            lambda request: HttpResponse("ok")
        )

    def test_preserves_valid_correlation_id(self):
        request = self.factory.get(
            "/",
            headers={"X-Correlation-ID": "request_123.test"},
        )

        response = self.middleware(request)

        self.assertEqual(request.correlation_id, "request_123.test")
        self.assertEqual(
            response["X-Correlation-ID"],
            "request_123.test",
        )

    def test_generates_id_when_header_is_missing(self):
        request = self.factory.get("/")

        response = self.middleware(request)

        self.assertEqual(
            uuid.UUID(response["X-Correlation-ID"]).version,
            4,
        )
        self.assertEqual(
            request.correlation_id,
            response["X-Correlation-ID"],
        )

    def test_replaces_invalid_correlation_id(self):
        request = self.factory.get(
            "/",
            headers={"X-Correlation-ID": "invalid value\n"},
        )

        response = self.middleware(request)

        self.assertNotEqual(
            response["X-Correlation-ID"],
            "invalid value\n",
        )
        self.assertEqual(
            uuid.UUID(response["X-Correlation-ID"]).version,
            4,
        )
