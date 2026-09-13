from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.policies import require_active_user

from .models import Notification
from .services import mark_notification_read


@login_required
def notification_list(request):
    require_active_user(request.user)
    notifications = Notification.objects.filter(recipient=request.user)
    return render(
        request,
        "notifications/notification_list.html",
        {"notifications": notifications},
    )


@require_POST
@login_required
def notification_mark_read(request, notification_id):
    require_active_user(request.user)
    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    mark_notification_read(
        actor=request.user, notification_id=notification.pk
    )
    return redirect("notifications:list")
