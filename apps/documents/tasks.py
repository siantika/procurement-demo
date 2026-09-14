import hashlib
import logging
import uuid
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from .choices import GenerationJobStatus
from .models import DocumentGenerationJob
from .renderers import render_pdf_v1
from .services import (
    claim_generation_job,
    complete_generation_job,
    fail_generation_job,
    publish_generation_job,
    release_generation_job_for_retry,
)
from .signature_images import load_signature_image_data_uri
from .storage import (
    read_private_object,
    stat_private_object,
    store_private_object,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    soft_time_limit=settings.DOCUMENT_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.DOCUMENT_HARD_TIME_LIMIT_SECONDS,
    name="apps.documents.tasks.execute_generation_job",
)
def execute_generation_job(self, job_id, correlation_id=None):
    correlation_id = str(correlation_id or job_id)
    job = claim_generation_job(
        job_id=job_id, correlation_id=correlation_id
    )
    if job is None:
        return {"job_id": str(job_id), "claimed": False}
    diagnostic_reference = str(self.request.id or uuid.uuid4())
    try:
        signature_image = load_signature_image_data_uri(
            job.input_snapshot
        )
        content = render_pdf_v1(
            job.input_snapshot,
            signature_image_data_uri=signature_image,
        )
        if not content.startswith(b"%PDF-"):
            raise ValueError("Renderer tidak menghasilkan PDF valid.")
        if len(content) > settings.DOCUMENT_MAX_PDF_BYTES:
            raise ValueError("Ukuran PDF melewati batas aplikasi.")
        sha256 = hashlib.sha256(content).hexdigest()
        object_key = (
            f"documents/{job.bid_revision_id}/"
            f"{job.bid_revision.revision_number}/"
            f"{job.document_version}/{job.pk}.pdf"
        )
        stored = store_private_object(
            object_key=object_key,
            content=content,
            content_type="application/pdf",
        )
        document = complete_generation_job(
            job_id=job.pk,
            object_key=stored.object_key,
            object_version_id=stored.version_id,
            size_bytes=len(content),
            sha256=sha256,
            correlation_id=correlation_id,
        )
        return {
            "job_id": str(job.pk),
            "claimed": True,
            "status": GenerationJobStatus.COMPLETED,
            "document_id": str(document.pk),
        }
    except SoftTimeLimitExceeded:
        error_code = "DOCUMENT_TIMEOUT"
        safe_message = "Pembuatan dokumen melewati batas waktu."
    except Exception:
        logger.exception(
            "Document generation failed",
            extra={"generation_job_id": str(job.pk)},
        )
        error_code = "DOCUMENT_TECHNICAL_ERROR"
        safe_message = (
            "Dokumen final tidak dapat dibuat. Silakan coba lagi."
        )
    if job.attempt_count < 3:
        release_generation_job_for_retry(job_id=job.pk)
        countdown = (10, 30, 90)[job.attempt_count - 1]
        raise self.retry(countdown=countdown, max_retries=3)
    fail_generation_job(
        job_id=job.pk,
        safe_error_code=error_code,
        safe_error_message=safe_message,
        diagnostic_reference=diagnostic_reference,
        correlation_id=correlation_id,
    )
    return {
        "job_id": str(job.pk),
        "claimed": True,
        "status": GenerationJobStatus.FAILED,
    }


@shared_task(name="apps.documents.tasks.reconcile_pending_jobs")
def reconcile_pending_jobs():
    cutoff = timezone.now() - timedelta(
        seconds=settings.DOCUMENT_RECONCILIATION_GRACE_SECONDS
    )
    job_ids = list(
        DocumentGenerationJob.objects.filter(
            status=GenerationJobStatus.PENDING,
            created_at__lte=cutoff,
        ).values_list("pk", flat=True)[:100]
    )
    for job_id in job_ids:
        publish_generation_job(job_id, job_id)
    stale_cutoff = timezone.now() - timedelta(
        seconds=(
            settings.DOCUMENT_HARD_TIME_LIMIT_SECONDS
            + settings.DOCUMENT_RECONCILIATION_GRACE_SECONDS
        )
    )
    stale_jobs = list(
        DocumentGenerationJob.objects.select_related("bid_revision")
        .filter(
            status=GenerationJobStatus.RUNNING,
            started_at__lte=stale_cutoff,
        )[:100]
    )
    for job in stale_jobs:
        object_key = (
            f"documents/{job.bid_revision_id}/"
            f"{job.bid_revision.revision_number}/"
            f"{job.document_version}/{job.pk}.pdf"
        )
        try:
            stored = stat_private_object(object_key)
            content = read_private_object(object_key)
            complete_generation_job(
                job_id=job.pk,
                object_key=object_key,
                object_version_id=stored.version_id,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                correlation_id=job.pk,
            )
        except Exception:
            logger.exception(
                "Stale document job recovery will republish",
                extra={"generation_job_id": str(job.pk)},
            )
            released = release_generation_job_for_retry(job_id=job.pk)
            if released is not None:
                publish_generation_job(job.pk, job.pk)
    return len(job_ids) + len(stale_jobs)
