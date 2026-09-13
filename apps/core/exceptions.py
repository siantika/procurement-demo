from django.core.exceptions import ValidationError


class ConcurrencyConflict(ValidationError):
    """State berubah setelah user membaca data atau terjadi write race."""


class InvalidTransition(ValidationError):
    """Entity tidak berada pada state yang mengizinkan command."""
