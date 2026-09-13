from django.urls import path

from . import views

app_name = "sourcing"

urlpatterns = [
    path("results/", views.result_list, name="result-list"),
    path("results/new/", views.result_create, name="result-create"),
    path(
        "results/<uuid:result_id>/",
        views.result_detail,
        name="result-detail",
    ),
    path(
        "results/<uuid:result_id>/edit/",
        views.result_update,
        name="result-update",
    ),
    path(
        "results/<uuid:result_id>/validate/",
        views.result_validate,
        name="result-validate",
    ),
    path(
        "results/<uuid:result_id>/customize/",
        views.result_customize,
        name="result-customize",
    ),
    path(
        "results/<uuid:result_id>/select/",
        views.result_select,
        name="result-select",
    ),
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
