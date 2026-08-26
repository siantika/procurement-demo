from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def user_in_group(user, group_name: str) -> bool:
    if not user.is_authenticated:
        return False

    return user.groups.filter(name=group_name).exists()


def user_in_any_group(user, group_names: list[str]) -> bool:
    if not user.is_authenticated:
        return False

    return user.groups.filter(name__in=group_names).exists()


def group_required(group_name: str):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            if not user_in_group(user, group_name):
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def any_group_required(group_names: list[str]):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            if not user_in_any_group(user, group_names):
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator