from django.contrib import admin

from .models import DocumentGenerationJob, FinalDocument


@admin.register(DocumentGenerationJob)
class DocumentGenerationJobAdmin(admin.ModelAdmin):
    list_display = (
        "id", "bid_revision", "document_version", "status",
        "attempt_count", "created_at"
    )
    list_filter = ("status", "template_version")
    readonly_fields = tuple(
        field.name for field in DocumentGenerationJob._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinalDocument)
class FinalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_number", "bid_revision", "document_version",
        "size_bytes", "created_at"
    )
    readonly_fields = tuple(
        field.name for field in FinalDocument._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
