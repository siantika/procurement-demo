from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.choices import UserRole
from apps.accounts.policies import require_valid_role
from apps.bids.choices import BidStatus
from apps.bids.models import BidProposalRevision
from apps.documents.choices import GenerationJobStatus
from apps.documents.models import DocumentGenerationJob
from apps.optimization.choices import OptimizationStatus
from apps.optimization.models import OptimizationRun
from config.metrics import snapshot_http_metrics


@login_required
def dashboard_view(request):
    require_valid_role(request.user)
    context = {
        "pending_approval_count": 0,
        "rejected_bid_count": 0,
        "active_optimization_count": 0,
    }
    if request.user.role == UserRole.MANAGER:
        context["pending_approval_count"] = (
            BidProposalRevision.objects.filter(
                status=BidStatus.WAITING_APPROVAL
            ).count()
        )
    elif request.user.role == UserRole.PROCUREMENT_STAFF:
        context["rejected_bid_count"] = (
            BidProposalRevision.objects.filter(
                status=BidStatus.REJECTED,
                revision_number=F(
                    "bid_proposal__current_revision_number"
                ),
            ).count()
        )
        context["active_optimization_count"] = (
            OptimizationRun.objects.filter(
                status__in=(
                    OptimizationStatus.PENDING,
                    OptimizationStatus.RUNNING,
                )
            ).count()
        )
    return render(request, "dashboard.html", context)


def health_live(request):
    return JsonResponse({"status": "ok"})


def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        executor = MigrationExecutor(connection)
        migrations_current = not executor.migration_plan(
            executor.loader.graph.leaf_nodes()
        )
    except Exception:
        return JsonResponse({"status": "not_ready"}, status=503)
    if not migrations_current:
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})


def _age_seconds(value, now):
    return max((now - value).total_seconds(), 0) if value else 0


def metrics_view(request):
    counts, durations = snapshot_http_metrics()
    lines = [
        "# HELP procurement_http_requests_total HTTP requests.",
        "# TYPE procurement_http_requests_total counter",
    ]
    for (method, route, status, outcome), value in sorted(counts.items()):
        labels = (
            f'method="{method}",route="{route}",'
            f'status="{status}",outcome="{outcome}"'
        )
        lines.append(
            f"procurement_http_requests_total{{{labels}}} {value}"
        )
    lines.extend(
        [
            "# HELP procurement_http_request_duration_seconds_total "
            "Accumulated HTTP request duration.",
            "# TYPE procurement_http_request_duration_seconds_total "
            "counter",
        ]
    )
    for (method, route), value in sorted(durations.items()):
        labels = f'method="{method}",route="{route}"'
        lines.append(
            "procurement_http_request_duration_seconds_total"
            f"{{{labels}}} {value:.6f}"
        )
    for status in OptimizationStatus.values:
        count = OptimizationRun.objects.filter(status=status).count()
        lines.append(
            "procurement_optimization_runs_total"
            f'{{status="{status}"}} {count}'
        )
    for status in GenerationJobStatus.values:
        count = DocumentGenerationJob.objects.filter(status=status).count()
        lines.append(
            "procurement_document_jobs_total"
            f'{{status="{status}"}} {count}'
        )
    now = timezone.now()
    oldest_run = OptimizationRun.objects.filter(
        status=OptimizationStatus.PENDING
    ).order_by("created_at").values_list("created_at", flat=True).first()
    oldest_job = DocumentGenerationJob.objects.filter(
        status=GenerationJobStatus.PENDING
    ).order_by("created_at").values_list("created_at", flat=True).first()
    lines.append(
        "procurement_oldest_pending_optimization_seconds "
        f"{_age_seconds(oldest_run, now):.3f}"
    )
    lines.append(
        "procurement_oldest_pending_document_seconds "
        f"{_age_seconds(oldest_job, now):.3f}"
    )
    return HttpResponse(
        "\n".join(lines) + "\n",
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
