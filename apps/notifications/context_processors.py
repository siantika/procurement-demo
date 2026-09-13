from .models import Notification


def unread_notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_active:
        return {"toast_notifications": ()}
    notifications = Notification.objects.filter(
        recipient=user,
        read_at__isnull=True,
    )[:3]
    return {"toast_notifications": notifications}
