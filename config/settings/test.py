"""Automated test settings."""

from config.env import database_from_url, env

from .base import *  # noqa: F403

SECRET_KEY = "django-insecure-automated-tests-only"
APP_ENV = "test"

DATABASES = {
    "default": database_from_url(
        env("TEST_DATABASE_URL", default="postgresql:///procurement_test"),
    ),
}

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
