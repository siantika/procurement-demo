import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .choices import OptimizationStatus


class OptimizationRun(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    tender_request = models.ForeignKey(
        "tender.TenderRequest",
        on_delete=models.PROTECT,
        related_name="optimization_runs",
    )
    tender_revision = models.ForeignKey(
        "tender.TenderRequestRevision",
        on_delete=models.PROTECT,
        related_name="optimization_runs",
    )
    retry_of_run = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="retry_runs",
    )
    status = models.CharField(
        max_length=20,
        choices=OptimizationStatus.choices,
        default=OptimizationStatus.PENDING,
    )
    algorithm_version = models.CharField(max_length=32)
    snapshot_schema_version = models.PositiveIntegerField()
    input_snapshot = models.JSONField()
    input_hash = models.CharField(max_length=64)
    result_count = models.PositiveIntegerField(default=0)
    safe_error_code = models.CharField(
        max_length=64, null=True, blank=True
    )
    safe_error_message = models.TextField(null=True, blank=True)
    diagnostic_reference = models.CharField(
        max_length=100, null=True, blank=True
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_optimization_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "optimization_optimization_run"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("tender_request", "-created_at"),
                name="opt_run_tender_created_idx",
            ),
            models.Index(
                fields=("status", "created_at"),
                name="opt_run_status_created_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("tender_request",),
                condition=models.Q(
                    status__in=(
                        OptimizationStatus.PENDING,
                        OptimizationStatus.RUNNING,
                    )
                ),
                name="optimization_one_active_run_per_tender",
            ),
            models.CheckConstraint(
                condition=models.Q(snapshot_schema_version__gt=0),
                name="optimization_snapshot_schema_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="optimization_run_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=OptimizationStatus.PENDING,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        safe_error_code__isnull=True,
                        safe_error_message__isnull=True,
                        diagnostic_reference__isnull=True,
                        result_count=0,
                    )
                    | models.Q(
                        status=OptimizationStatus.RUNNING,
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        safe_error_code__isnull=True,
                        safe_error_message__isnull=True,
                        diagnostic_reference__isnull=True,
                        result_count=0,
                    )
                    | models.Q(
                        status=OptimizationStatus.COMPLETED,
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        safe_error_code__isnull=True,
                        safe_error_message__isnull=True,
                        diagnostic_reference__isnull=True,
                    )
                    | models.Q(
                        status=OptimizationStatus.FAILED,
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        safe_error_code__isnull=False,
                        safe_error_message__isnull=False,
                        diagnostic_reference__isnull=False,
                        result_count=0,
                    )
                ),
                name="optimization_run_state_payload_valid",
            ),
        ]

    @property
    def is_terminal(self):
        return self.status in {
            OptimizationStatus.COMPLETED,
            OptimizationStatus.FAILED,
        }

    def clean(self):
        super().clean()
        if (
            self.tender_revision_id
            and self.tender_request_id
            and self.tender_revision.tender_request_id
            != self.tender_request_id
        ):
            raise ValidationError(
                {
                    "tender_revision": (
                        "Revision harus berasal dari Tender yang sama."
                    )
                }
            )
        if self.retry_of_run_id:
            original = self.retry_of_run
            if original.tender_request_id != self.tender_request_id:
                raise ValidationError(
                    {"retry_of_run": "Retry harus untuk Tender yang sama."}
                )
            if original.status != OptimizationStatus.FAILED:
                raise ValidationError(
                    {
                        "retry_of_run": (
                            "Hanya run gagal yang dapat di-retry."
                        )
                    }
                )

    def __str__(self):
        return f"{self.tender_request.internal_code} / {self.status}"


class ImmutableRejectionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Candidate rejection tidak dapat diubah.")

    def delete(self):
        raise ValidationError("Candidate rejection tidak dapat dihapus.")


class OptimizationCandidateRejection(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    optimization_run = models.ForeignKey(
        OptimizationRun,
        on_delete=models.CASCADE,
        related_name="candidate_rejections",
    )
    candidate_identifier = models.CharField(max_length=128)
    reason_code = models.CharField(max_length=64)
    safe_detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableRejectionQuerySet)()

    class Meta:
        db_table = "optimization_candidate_rejection"
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("optimization_run", "candidate_identifier"),
                name="optimization_rejection_candidate_unique",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Candidate rejection tidak dapat diubah."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Candidate rejection tidak dapat dihapus.")
