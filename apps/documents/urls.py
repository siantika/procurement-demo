from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path(
        "bids/<uuid:revision_id>/finalize/",
        views.document_finalize,
        name="finalize",
    ),
    path("jobs/<uuid:job_id>/", views.job_detail, name="job-detail"),
    path(
        "jobs/<uuid:job_id>/status/",
        views.job_status,
        name="job-status",
    ),
    path(
        "<uuid:document_id>/download/",
        views.document_download,
        name="download",
    ),
]
