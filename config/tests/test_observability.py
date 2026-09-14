import json
import logging
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from config.logging import JsonLogFormatter


class HealthAndMetricsTests(TestCase):
    def test_live_and_ready_are_public_and_minimal(self):
        live = self.client.get(reverse("health-live"))
        ready = self.client.get(reverse("health-ready"))

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "ok"})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {"status": "ready"})

    def test_ready_returns_safe_failure_without_details(self):
        with patch(
            "config.views.connection.cursor",
            side_effect=RuntimeError("database secret"),
        ):
            response = self.client.get(reverse("health-ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready"})
        self.assertNotContains(
            response, "database secret", status_code=503
        )

    def test_metrics_use_bounded_route_labels(self):
        self.client.get(reverse("health-live"))
        response = self.client.get(reverse("metrics"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "procurement_http_requests_total")
        self.assertContains(response, 'route="health-live"')
        self.assertContains(
            response, "procurement_document_jobs_total"
        )


class JsonLogFormatterTests(TestCase):
    def test_emits_structured_fields(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="completed",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "correlation-test"
        record.status_code = 200

        payload = json.loads(JsonLogFormatter().format(record))

        self.assertEqual(payload["message"], "completed")
        self.assertIn("process", payload)
        self.assertIn("environment", payload)
        self.assertEqual(payload["correlation_id"], "correlation-test")
        self.assertEqual(payload["status_code"], 200)
