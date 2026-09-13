from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "type", "title", "read_at", "created_at")
    list_filter = ("type", "read_at")
    search_fields = ("recipient__username", "title")
    readonly_fields = ("source_event_id", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
