from django.contrib import admin

from .models import Signature


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ("bid_revision", "signer_name", "signed_at")
    readonly_fields = tuple(
        field.name for field in Signature._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
