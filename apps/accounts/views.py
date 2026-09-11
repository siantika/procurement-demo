"""HTTP views untuk autentikasi dan halaman akun pengguna."""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render

from .forms import LoginForm
from .rate_limits import (
    clear_login_failures,
    is_login_blocked,
    record_login_failure,
)


class AccountLoginView(LoginView):
    """Menampilkan form dan membuat session untuk login yang valid."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if is_login_blocked(request):
            self._login_was_blocked = True
            form = self.get_form()
            form.add_error(
                None,
                "Login sementara dibatasi. Coba lagi beberapa menit.",
            )
            return self.form_invalid(form)

        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        if not getattr(self, "_login_was_blocked", False):
            record_login_failure(self.request)
        return super().form_invalid(form)

    def form_valid(self, form):
        clear_login_failures(self.request)
        return super().form_valid(form)


class AccountLogoutView(LogoutView):
    """Menghapus session melalui request POST."""

    http_method_names = ["post", "options"]


@login_required
def profile_view(request):
    """Menampilkan profil milik pengguna yang sedang login."""

    return render(request, "accounts/profile.html")
