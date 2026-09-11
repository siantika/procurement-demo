"""Konfigurasi pengelolaan custom User melalui Django Admin."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .choices import UserRole
from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import User


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    """Admin user dengan akses berbasis role bisnis."""

    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    model = User

    list_display = (
        "username",
        "email",
        "full_name",
        "role",
        "is_active",
    )
    list_filter = ("role", "is_active")
    search_fields = ("username", "email", "full_name")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Informasi pengguna",
            {"fields": ("email", "full_name", "role")},
        ),
        ("Status", {"fields": ("is_active",)}),
        (
            "Riwayat",
            {
                "classes": ("collapse",),
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "full_name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = (
        "last_login",
        "date_joined",
        "created_at",
        "updated_at",
    )

    @staticmethod
    def _can_manage_users(user):
        """Izinkan superuser atau user aktif dengan role ADMIN."""

        return user.is_active and (
            user.is_superuser or user.role == UserRole.ADMIN
        )

    def has_module_permission(self, request):
        return self._can_manage_users(request.user)

    def has_view_permission(self, request, obj=None):
        return self._can_manage_users(request.user)

    def has_add_permission(self, request):
        return self._can_manage_users(request.user)

    def has_change_permission(self, request, obj=None):
        return self._can_manage_users(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """Sinkronkan akses admin dengan role bisnis sebelum menyimpan."""

        obj.is_staff = obj.role == UserRole.ADMIN
        super().save_model(request, obj, form, change)
