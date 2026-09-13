from django.urls import path

from . import views

app_name = "bids"

urlpatterns = [
    path("", views.bid_list, name="list"),
    path(
        "tenders/<uuid:tender_id>/create/",
        views.bid_create,
        name="create",
    ),
    path("<uuid:proposal_id>/", views.bid_detail, name="detail"),
    path(
        "revisions/<uuid:revision_id>/",
        views.bid_revision_detail,
        name="revision-detail",
    ),
    path(
        "<uuid:proposal_id>/pricing/", views.bid_price, name="price"
    ),
    path(
        "<uuid:proposal_id>/submit/", views.bid_submit, name="submit"
    ),
    path(
        "<uuid:proposal_id>/revise/", views.bid_revise, name="revise"
    ),
]
