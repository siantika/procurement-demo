from django.contrib import admin

from .models import (
    ProcurementResult,
    ProcurementResultItem,
    ProcurementResultSelection,
    SupplierAllocation,
    SupplierOffer,
)


class ReadOnlySourcingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SupplierOffer)
class SupplierOfferAdmin(ReadOnlySourcingAdmin):
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


@admin.register(ProcurementResult)
class ProcurementResultAdmin(ReadOnlySourcingAdmin):
    list_display = (
        "tender_revision",
        "source_type",
        "status",
        "total_purchase",
        "version",
    )
    list_filter = ("source_type", "status")
    search_fields = ("tender_revision__tender_request__internal_code",)


@admin.register(ProcurementResultItem)
class ProcurementResultItemAdmin(ReadOnlySourcingAdmin):
    list_display = (
        "procurement_result",
        "line_number",
        "requested_quantity_snapshot",
        "item_purchase_total",
    )


@admin.register(SupplierAllocation)
class SupplierAllocationAdmin(ReadOnlySourcingAdmin):
    list_display = (
        "procurement_result_item",
        "supplier_offer",
        "allocated_quantity",
        "allocation_purchase",
    )


@admin.register(ProcurementResultSelection)
class ProcurementResultSelectionAdmin(ReadOnlySourcingAdmin):
    list_display = (
        "tender_request",
        "selection_number",
        "procurement_result",
        "selected_by",
        "selected_at",
    )
