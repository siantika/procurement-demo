from django.contrib import admin

from .models import BidProposal, BidProposalItem, BidProposalRevision


class BidRevisionInline(admin.TabularInline):
    model = BidProposalRevision
    extra = 0
    can_delete = False
    fields = ("revision_number", "status", "selected_result", "version")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BidProposal)
class BidProposalAdmin(admin.ModelAdmin):
    list_display = (
        "proposal_number",
        "tender_request",
        "current_revision_number",
        "created_at",
    )
    search_fields = ("proposal_number", "tender_request__internal_code")
    readonly_fields = [field.name for field in BidProposal._meta.fields]
    inlines = (BidRevisionInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BidProposalRevision)
class BidProposalRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "bid_proposal",
        "revision_number",
        "status",
        "total_bid_value",
        "updated_at",
    )
    list_filter = ("status",)
    readonly_fields = [
        field.name for field in BidProposalRevision._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BidProposalItem)
class BidProposalItemAdmin(admin.ModelAdmin):
    list_display = (
        "bid_revision",
        "line_number",
        "item_bid_total",
    )
    readonly_fields = [
        field.name for field in BidProposalItem._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
