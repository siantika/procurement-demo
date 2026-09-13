from django.urls import path

from . import views

app_name = "sourcing"

urlpatterns = [
    path("offers/", views.offer_list, name="offer-list"),
    path("offers/new/", views.offer_create, name="offer-create"),
    path(
        "offers/<uuid:offer_id>/",
        views.offer_detail,
        name="offer-detail",
    ),
    path(
        "offers/<uuid:offer_id>/edit/",
        views.offer_update,
        name="offer-update",
    ),
    path(
        "offers/<uuid:offer_id>/supersede/",
        views.offer_supersede,
        name="offer-supersede",
    ),
    path(
        "offers/<uuid:offer_id>/deactivate/",
        views.offer_deactivate,
        name="offer-deactivate",
    ),
]
