from django.contrib import admin

from .models import OptimizationCandidateRejection, OptimizationRun


class CandidateRejectionInline(admin.TabularInline):
    model = OptimizationCandidateRejection
    extra = 0
    can_delete = False
    readonly_fields = (
        "candidate_identifier",
        "reason_code",
        "safe_detail",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OptimizationRun)
class OptimizationRunAdmin(admin.ModelAdmin):
    list_display = (
        "tender_request",
        "status",
        "result_count",
        "algorithm_version",
        "created_at",
    )
    list_filter = ("status", "algorithm_version")
    readonly_fields = [
        field.name for field in OptimizationRun._meta.fields
    ]
    inlines = (CandidateRejectionInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
