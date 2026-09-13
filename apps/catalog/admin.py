from django.contrib import admin

from .models import Product, Supplier


class ReadOnlyBusinessAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(ReadOnlyBusinessAdmin):
    list_display = ("code", "name", "default_unit", "is_active", "version")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Supplier)
class SupplierAdmin(ReadOnlyBusinessAdmin):
    list_display = ("code", "name", "contact_name", "is_active", "version")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "contact_name")
