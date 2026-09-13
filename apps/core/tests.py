from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from .domain.canonical_json import canonical_dumps, canonical_hash


class CanonicalJsonTests(TestCase):
    def test_normalizes_values_and_sorts_object_keys(self):
        payload = {
            "z": Decimal("100.000"),
            "a": UUID("B06A05CD-2C44-4D86-BCCF-F455C25BCE31"),
            "time": datetime(2026, 9, 13, 3, 0, tzinfo=timezone.utc),
        }

        self.assertEqual(
            canonical_dumps(payload),
            (
                '{"a":"b06a05cd-2c44-4d86-bccf-f455c25bce31",'
                '"time":"2026-09-13T03:00:00Z","z":"100.000"}'
            ),
        )

    def test_same_content_has_same_hash(self):
        first = {"quantity": Decimal("1.000"), "name": "Pump"}
        second = {"name": "Pump", "quantity": Decimal("1.000")}

        self.assertEqual(canonical_hash(first), canonical_hash(second))
