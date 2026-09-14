"""Settings shared by every environment."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts.apps.AccountsConfig",
    "apps.approval.apps.ApprovalConfig",
    "apps.audit.apps.AuditConfig",
    "apps.bids.apps.BidsConfig",
    "apps.catalog.apps.CatalogConfig",
    "apps.documents.apps.DocumentsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.optimization.apps.OptimizationConfig",
    "apps.signatures.apps.SignaturesConfig",
    "apps.sourcing.apps.SourcingConfig",
    "apps.tender.apps.TenderConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.CorrelationIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                (
                    "apps.notifications.context_processors."
                    "unread_notifications"
                ),
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"
ACCOUNT_LOGIN_MAX_FAILURES = 5
ACCOUNT_LOGIN_WINDOW_SECONDS = 300

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ROUTES = {
    "apps.optimization.tasks.*": {"queue": "optimization"},
    "apps.documents.tasks.*": {"queue": "documents"},
}
CELERY_BEAT_SCHEDULE = {
    "reconcile-pending-optimization-runs": {
        "task": "apps.optimization.tasks.reconcile_pending_runs",
        "schedule": 60.0,
    },
    "reconcile-pending-document-jobs": {
        "task": "apps.documents.tasks.reconcile_pending_jobs",
        "schedule": 60.0,
    },
}

OPTIMIZER_MAX_ITEMS = 100
OPTIMIZER_MAX_OFFERS_PER_ITEM = 50
OPTIMIZER_MAX_RESULTS = 20
OPTIMIZER_EXPLORATION_LIMIT = 2_000
OPTIMIZER_SOFT_TIME_LIMIT_SECONDS = 240
OPTIMIZER_HARD_TIME_LIMIT_SECONDS = 300
OPTIMIZER_RECONCILIATION_GRACE_SECONDS = 60

MINIO_BUCKET = "procurement-private"
MINIO_SECURE = False

DOCUMENT_TEMPLATE_VERSION = "1"
DOCUMENT_SNAPSHOT_SCHEMA_VERSION = 1
DOCUMENT_SOFT_TIME_LIMIT_SECONDS = 50
DOCUMENT_HARD_TIME_LIMIT_SECONDS = 60
DOCUMENT_RECONCILIATION_GRACE_SECONDS = 60
DOCUMENT_MAX_PDF_BYTES = 10 * 1024 * 1024


# Gunakan custom user model milik aplikasi accounts.
AUTH_USER_MODEL = "accounts.User"
