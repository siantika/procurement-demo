from django.urls import path

from . import views

app_name = "tender"

urlpatterns = [
    path("", views.tender_list, name="list"),
    path("new/", views.tender_create, name="create"),
    path("<uuid:tender_id>/", views.tender_detail, name="detail"),
    path("<uuid:tender_id>/revise/", views.tender_revise, name="revise"),
]
