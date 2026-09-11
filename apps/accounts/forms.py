"""Form autentikasi dan administrasi user untuk modul accounts."""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.forms import CharField, PasswordInput, TextInput

User = get_user_model()


class LoginForm(AuthenticationForm):
    """Form login berbasis authentication backend Django."""

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


class AdminUserCreationForm(UserCreationForm):
    """Form Admin untuk membuat User baru dengan password yang di-hash."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "full_name", "role")


class AdminUserChangeForm(UserChangeForm):
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
