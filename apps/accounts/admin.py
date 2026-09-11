"""Konfigurasi pengelolaan custom User melalui Django Admin."""

import uuid

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .choices import UserRole
from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import User
from .services import save_user_from_admin


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
        """Izinkan hanya user aktif dengan role bisnis ADMIN."""

        return user.is_active and user.role == UserRole.ADMIN

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
        """Simpan dan audit melalui application service accounts."""

        correlation_id = getattr(
            request,
            "correlation_id",
            str(uuid.uuid4()),
        )
        save_user_from_admin(
            actor=request.user,
            user=obj,
            correlation_id=correlation_id,
        )
