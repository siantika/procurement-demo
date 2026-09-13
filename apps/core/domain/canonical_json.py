"""Canonical serialization untuk snapshot historis dan hashing."""

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID


def _normalize(value):
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value).lower()
    if isinstance(value, datetime):
        normalized = value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return value


def canonical_dumps(value):
    """Serialize value secara stabil untuk disimpan atau di-hash."""

    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_hash(value):
    """Kembalikan SHA-256 lowercase dari canonical JSON UTF-8."""

    payload = canonical_dumps(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
