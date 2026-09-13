from django.contrib import admin

from .models import TenderRequest, TenderRequestItem, TenderRequestRevision


class ReadOnlyTenderAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TenderRequest)
class TenderRequestAdmin(ReadOnlyTenderAdmin):
    list_display = (
        "internal_code",
        "current_revision_number",
        "version",
        "created_at",
    )
    search_fields = ("internal_code",)


@admin.register(TenderRequestRevision)
class TenderRequestRevisionAdmin(ReadOnlyTenderAdmin):
    list_display = (
        "tender_request",
        "revision_number",
        "institution_name",
        "title",
        "created_at",
    )
    search_fields = (
        "tender_request__internal_code",
        "institution_name",
        "title",
    )


@admin.register(TenderRequestItem)
class TenderRequestItemAdmin(ReadOnlyTenderAdmin):
    list_display = (
        "tender_revision",
        "line_number",
        "product",
        "requested_quantity",
        "unit",
    )
