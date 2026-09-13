from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.policies import require_procurement_staff
from apps.core.exceptions import InvalidTransition

from .models import OptimizationRun
from .services import request_optimization, retry_optimization


def _run_queryset():
    return OptimizationRun.objects.select_related(
        "tender_request", "tender_revision", "requested_by", "retry_of_run"
    ).prefetch_related("candidate_rejections", "procurement_results")


@login_required
def run_list(request):
    require_procurement_staff(request.user)
    return render(
        request,
        "optimization/run_list.html",
        {"runs": _run_queryset()},
    )


@login_required
def run_detail(request, run_id):
    require_procurement_staff(request.user)
    run = get_object_or_404(_run_queryset(), pk=run_id)
    return render(
        request,
        "optimization/run_detail.html",
        {
            "run": run,
            "results": run.procurement_results.order_by("rank"),
        },
    )


@require_POST
@login_required
def run_create(request, tender_id):
    require_procurement_staff(request.user)
    try:
        run = request_optimization(
            actor=request.user,
            tender_request_id=tender_id,
            correlation_id=request.correlation_id,
        )
    except (ValidationError, InvalidTransition) as error:
        messages.error(request, error.messages[0])
        return redirect("tender:detail", tender_id=tender_id)
    return redirect("optimization:run-detail", run_id=run.pk)


@require_POST
@login_required
def run_retry(request, run_id):
    require_procurement_staff(request.user)
    previous = get_object_or_404(OptimizationRun, pk=run_id)
    try:
        run = retry_optimization(
            actor=request.user,
            run_id=previous.pk,
            correlation_id=request.correlation_id,
        )
    except (ValidationError, InvalidTransition) as error:
        messages.error(request, error.messages[0])
        return redirect("optimization:run-detail", run_id=previous.pk)
    return redirect("optimization:run-detail", run_id=run.pk)


@require_GET
@login_required
def run_status(request, run_id):
    require_procurement_staff(request.user)
    run = get_object_or_404(OptimizationRun, pk=run_id)
    changed_at = run.completed_at or run.started_at or run.created_at
    return JsonResponse(
        {
            "status": run.status,
            "terminal": run.is_terminal,
            "safe_message": run.safe_error_message,
            "updated_at": changed_at.isoformat(),
            "result_count": run.result_count,
        }
    )
