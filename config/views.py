from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.policies import require_valid_role


@login_required
def dashboard_view(request):
    require_valid_role(request.user)
    return render(request, "dashboard.html")
