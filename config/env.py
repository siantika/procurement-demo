"""Small, dependency-free helpers for environment-based configuration."""

import os
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


def env(name: str, *, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_required(name: str) -> str:
    value = env(name).strip()
    if not value:
        raise RuntimeError(f"Environment variable must not be empty: {name}")
    return value


def env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"Invalid boolean value for {name}: {raw_value!r}")


def env_int(name: str, *, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer value for {name}: {raw_value!r}") from exc


def env_csv(
    name: str,
    *,
    default: str = "",
    required: bool = False,
) -> list[str]:
    raw_value = os.environ.get(name, default)
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    if required and not values:
        raise RuntimeError(f"Missing required comma-separated environment variable: {name}")
    return values


def database_from_url(url: str, *, conn_max_age: int = 0) -> dict[str, Any]:
    """Convert a PostgreSQL URL into a Django DATABASES entry."""

    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must use postgres:// or postgresql://")

    database_name = unquote(parsed.path.lstrip("/"))
    if not database_name:
        raise RuntimeError("DATABASE_URL must include a database name")

    options: dict[str, str] = {}
    query = parse_qs(parsed.query)
    if sslmode := query.get("sslmode"):
        options["sslmode"] = sslmode[-1]

    config: dict[str, Any] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": conn_max_age,
    }
    if options:
        config["OPTIONS"] = options
    return config
