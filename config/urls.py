"""URL utama untuk proyek procurement."""

from django.contrib import admin
from django.urls import include, path

from .views import (
    dashboard_view,
    health_live,
    health_ready,
    metrics_view,
)

urlpatterns = [
    path("health/live/", health_live, name="health-live"),
    path("health/ready/", health_ready, name="health-ready"),
    path("metrics/", metrics_view, name="metrics"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("approval/", include("apps.approval.urls")),
    path("bids/", include("apps.bids.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("documents/", include("apps.documents.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("optimization/", include("apps.optimization.urls")),
    path("sourcing/", include("apps.sourcing.urls")),
    path("signatures/", include("apps.signatures.urls")),
    path("tenders/", include("apps.tender.urls")),
    path("", dashboard_view, name="dashboard"),
]
