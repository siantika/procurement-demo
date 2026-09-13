from django.contrib import admin

from .models import ApprovalDecision


@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(admin.ModelAdmin):
    list_display = ("bid_revision", "decision", "decided_by", "decided_at")
    list_filter = ("decision",)
    readonly_fields = [
        field.name for field in ApprovalDecision._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
