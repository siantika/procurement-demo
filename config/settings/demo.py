"""Demo VPS settings."""

from config.env import (
    database_from_url,
    env,
    env_bool,
    env_csv,
    env_int,
    env_required,
)

from .base import *  # noqa: F403

MIDDLEWARE.insert(  # noqa: F405
    1, "whitenoise.middleware.WhiteNoiseMiddleware"
)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}

SECRET_KEY = env_required("DJANGO_SECRET_KEY")
APP_ENV = env("APP_ENV", default="demo")
DEBUG = False
ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", required=True)
CSRF_TRUSTED_ORIGINS = env_csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS", required=True
)

DATABASES = {
    "default": database_from_url(
        env_required("DATABASE_URL"),
        conn_max_age=60,
    ),
}

CELERY_BROKER_URL = env_required("CELERY_BROKER_URL")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env_required("DJANGO_CACHE_URL"),
    }
}

MINIO_ENDPOINT = env_required("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = env_required("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = env_required("MINIO_SECRET_KEY")
MINIO_BUCKET = env("MINIO_BUCKET", default=MINIO_BUCKET)  # noqa: F405
MINIO_SECURE = env_bool("MINIO_SECURE", default=True)

APP_BASE_URL = env_required("APP_BASE_URL")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env_bool(
    "DJANGO_SESSION_COOKIE_SECURE", default=True
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=True)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", default=3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
