from django.contrib import admin

from .models import SupplierOffer


@admin.register(SupplierOffer)
class SupplierOfferAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "product",
        "net_purchase_price",
        "available_quantity",
        "is_active",
        "version",
    )
    list_filter = ("is_active", "product")
    search_fields = ("supplier__code", "supplier__name", "product__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
