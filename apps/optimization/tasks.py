import logging
import time
import uuid
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from .choices import OptimizationStatus
from .models import OptimizationRun
from .services import (
    calculate_run_outcome,
    claim_optimization_run,
    complete_optimization_run,
    fail_optimization_run,
    publish_optimization_run,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    soft_time_limit=settings.OPTIMIZER_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.OPTIMIZER_HARD_TIME_LIMIT_SECONDS,
    name="apps.optimization.tasks.execute_optimization_run",
)
def execute_optimization_run(self, run_id, correlation_id=None):
    correlation_id = str(correlation_id or run_id)
    run = claim_optimization_run(
        run_id=run_id, correlation_id=correlation_id
    )
    if run is None:
        return {"run_id": str(run_id), "claimed": False}
    started = time.monotonic()
    soft_limit = settings.OPTIMIZER_SOFT_TIME_LIMIT_SECONDS
    diagnostic_reference = str(self.request.id or uuid.uuid4())
    try:
        outcome = calculate_run_outcome(
            run=run,
            should_stop=lambda: time.monotonic() - started
            >= max(soft_limit - 1, 0),
        )
        completed = complete_optimization_run(
            run_id=run.pk,
            outcome=outcome,
            correlation_id=correlation_id,
        )
        return {
            "run_id": str(completed.pk),
            "claimed": True,
            "status": completed.status,
            "result_count": completed.result_count,
        }
    except SoftTimeLimitExceeded:
        fail_optimization_run(
            run_id=run.pk,
            safe_error_code="OPTIMIZATION_TIMEOUT",
            safe_error_message="Optimization melewati batas waktu.",
            diagnostic_reference=diagnostic_reference,
            correlation_id=correlation_id,
        )
    except Exception:
        logger.exception(
            "Optimization run failed",
            extra={
                "correlation_id": correlation_id,
                "operation": "execute_optimization_run",
                "entity_type": "OptimizationRun",
                "entity_id": str(run.pk),
                "outcome": "error",
                "safe_error_code": "OPTIMIZATION_TECHNICAL_ERROR",
                "diagnostic_reference": diagnostic_reference,
            },
        )
        fail_optimization_run(
            run_id=run.pk,
            safe_error_code="OPTIMIZATION_TECHNICAL_ERROR",
            safe_error_message=(
                "Optimization tidak dapat diselesaikan. Silakan coba lagi."
            ),
            diagnostic_reference=diagnostic_reference,
            correlation_id=correlation_id,
        )
    return {
        "run_id": str(run.pk),
        "claimed": True,
        "status": OptimizationStatus.FAILED,
    }


@shared_task(name="apps.optimization.tasks.reconcile_pending_runs")
def reconcile_pending_runs():
    cutoff = timezone.now() - timedelta(
        seconds=settings.OPTIMIZER_RECONCILIATION_GRACE_SECONDS
    )
    run_ids = list(
        OptimizationRun.objects.filter(
            status=OptimizationStatus.PENDING,
            created_at__lte=cutoff,
        ).values_list("pk", flat=True)[:100]
    )
    for run_id in run_ids:
        publish_optimization_run(run_id, run_id)
    return len(run_ids)
