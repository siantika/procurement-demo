from django.urls import path

from . import views

app_name = "approval"

urlpatterns = [
    path("", views.approval_queue, name="queue"),
    path(
        "<uuid:revision_id>/", views.approval_detail, name="detail"
    ),
    path(
        "<uuid:revision_id>/approve/",
        views.approval_approve,
        name="approve",
    ),
    path(
        "<uuid:revision_id>/reject/",
        views.approval_reject_form,
        name="reject-form",
    ),
    path(
        "<uuid:revision_id>/reject/submit/",
        views.approval_reject,
        name="reject",
    ),
]
