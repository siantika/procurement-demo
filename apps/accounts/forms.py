"""Form autentikasi dan administrasi user untuk modul accounts."""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django.forms import CharField, PasswordInput, TextInput

User = get_user_model()


class CaseInsensitiveIdentityMixin:
    """Validasi identity sebelum constraint mencapai database."""

    def _validate_identity(self, field_name, value):
        lookup = {f"{field_name}__iexact": value}
        matches = User.objects.filter(**lookup)
        if self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            label = self.fields[field_name].label or field_name
            raise ValidationError(f"{label} sudah digunakan.")
        return value

    def clean_username(self):
        username = self.cleaned_data["username"]
        return self._validate_identity("username", username)

    def clean_email(self):
        email = self.cleaned_data["email"]
        return self._validate_identity("email", email)


class LoginForm(AuthenticationForm):
    """Form login berbasis authentication backend Django."""

    error_messages = {
        "invalid_login": "Username atau password salah.",
        "inactive": "Username atau password salah.",
    }

    username = CharField(
        widget=TextInput(
            attrs={
                "autocomplete": "username",
                "autofocus": True,
            }
        )
    )
    password = CharField(
        strip=False,
        widget=PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class AdminUserCreationForm(
    CaseInsensitiveIdentityMixin,
    UserCreationForm,
):
    """Form Admin untuk membuat User baru dengan password yang di-hash."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "full_name", "role")


class AdminUserChangeForm(CaseInsensitiveIdentityMixin, UserChangeForm):
    """Form Admin untuk mengubah User tanpa mengekspos password."""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "username",
            "password",
            "email",
            "full_name",
            "role",
            "is_active",
        )
