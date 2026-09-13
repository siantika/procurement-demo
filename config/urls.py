"""URL utama untuk proyek procurement."""

from django.contrib import admin
from django.urls import include, path

from .views import dashboard_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("sourcing/", include("apps.sourcing.urls")),
    path("tenders/", include("apps.tender.urls")),
    path("", dashboard_view, name="dashboard"),
]
