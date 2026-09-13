from django.urls import path

from . import views

app_name = "optimization"

urlpatterns = [
    path("", views.run_list, name="run-list"),
    path(
        "tenders/<uuid:tender_id>/runs/",
        views.run_create,
        name="run-create",
    ),
    path("runs/<uuid:run_id>/", views.run_detail, name="run-detail"),
    path(
        "runs/<uuid:run_id>/status/",
        views.run_status,
        name="run-status",
    ),
    path(
        "runs/<uuid:run_id>/retry/",
        views.run_retry,
        name="run-retry",
    ),
]
