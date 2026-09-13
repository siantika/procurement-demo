from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.product_list, name="product-list"),
    path("products/new/", views.product_create, name="product-create"),
    path(
        "products/<uuid:product_id>/",
        views.product_detail,
        name="product-detail",
    ),
    path(
        "products/<uuid:product_id>/edit/",
        views.product_update,
        name="product-update",
    ),
    path(
        "products/<uuid:product_id>/deactivate/",
        views.product_deactivate,
        name="product-deactivate",
    ),
    path(
        "products/<uuid:product_id>/reactivate/",
        views.product_reactivate,
        name="product-reactivate",
    ),
    path("suppliers/", views.supplier_list, name="supplier-list"),
    path("suppliers/new/", views.supplier_create, name="supplier-create"),
    path(
        "suppliers/<uuid:supplier_id>/",
        views.supplier_detail,
        name="supplier-detail",
    ),
    path(
        "suppliers/<uuid:supplier_id>/edit/",
        views.supplier_update,
        name="supplier-update",
    ),
    path(
        "suppliers/<uuid:supplier_id>/deactivate/",
        views.supplier_deactivate,
        name="supplier-deactivate",
    ),
]
