"""Local development settings."""

from config.env import database_from_url, env, env_bool, env_csv

from .base import *  # noqa: F403

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-local-development-only",
)
DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env_csv(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1,[::1]",
)
CSRF_TRUSTED_ORIGINS = env_csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="http://localhost:8000,http://127.0.0.1:8000",
)

DATABASES = {
    "default": database_from_url(
        env("DATABASE_URL", default="postgresql:///procurement"),
    ),
}

CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0"
)
CELERY_TASK_ALWAYS_EAGER = env_bool(
    "CELERY_TASK_ALWAYS_EAGER", default=False
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env(
            "DJANGO_CACHE_URL",
            default="redis://127.0.0.1:6379/1",
        ),
    }
}

MINIO_ENDPOINT = env("MINIO_ENDPOINT", default="127.0.0.1:9000")
MINIO_ACCESS_KEY = env("MINIO_ACCESS_KEY", default="minioadmin")
MINIO_SECRET_KEY = env("MINIO_SECRET_KEY", default="minioadmin")
MINIO_BUCKET = env("MINIO_BUCKET", default=MINIO_BUCKET)  # noqa: F405
MINIO_SECURE = env_bool("MINIO_SECURE", default=False)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
