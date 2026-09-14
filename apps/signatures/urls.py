from django.urls import path

from . import views

app_name = "signatures"

urlpatterns = [
    path(
        "<uuid:revision_id>/sign/",
        views.signature_sign,
        name="sign",
    )
]
