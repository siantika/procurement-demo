"""HTTP views untuk autentikasi dan halaman akun pengguna."""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render

from .forms import LoginForm


class AccountLoginView(LoginView):
    """Menampilkan form dan membuat session untuk login yang valid."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    """Menghapus session melalui request POST."""

    http_method_names = ["post", "options"]


@login_required
def profile_view(request):
    """Menampilkan profil milik pengguna yang sedang login."""

    return render(request, "accounts/profile.html")
