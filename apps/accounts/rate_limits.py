"""Cache-backed rate limiting untuk percobaan login."""

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import salted_hmac


def _login_key(request):
    identity = request.POST.get("username", "").strip().casefold()[:150]
    source_address = str(request.META.get("REMOTE_ADDR", "unknown"))[:64]
    digest = salted_hmac(
        "accounts.login-rate-limit",
        f"{identity}\0{source_address}",
    ).hexdigest()
    return f"accounts:login-failures:{digest}"


def is_login_blocked(request):
    """Return True jika kombinasi identity/source melewati batas."""

    failures = cache.get(_login_key(request), 0)
    return failures >= settings.ACCOUNT_LOGIN_MAX_FAILURES


def record_login_failure(request):
    """Catat kegagalan tanpa menyimpan username atau alamat sumber."""

    key = _login_key(request)
    timeout = settings.ACCOUNT_LOGIN_WINDOW_SECONDS
    if cache.add(key, 1, timeout=timeout):
        return 1

    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def clear_login_failures(request):
    """Hapus kegagalan setelah kombinasi yang sama berhasil login."""

    cache.delete(_login_key(request))
