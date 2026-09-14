import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .choices import GenerationJobStatus


class DocumentNumberSequence(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documents_number_sequence"


class DocumentGenerationJob(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    bid_revision = models.ForeignKey(
        "bids.BidProposalRevision",
        on_delete=models.PROTECT,
        related_name="generation_jobs",
    )
    status = models.CharField(
        max_length=20,
        choices=GenerationJobStatus.choices,
        default=GenerationJobStatus.PENDING,
    )
    document_version = models.PositiveIntegerField()
    template_version = models.CharField(max_length=32, default="1")
    snapshot_schema_version = models.PositiveIntegerField()
    input_snapshot = models.JSONField()
    input_hash = models.CharField(max_length=64)
    attempt_count = models.PositiveIntegerField(default=0)
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
        related_name="requested_document_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "documents_generation_job"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("status", "created_at"),
                name="document_job_status_idx",
            ),
            models.Index(
                fields=("bid_revision", "-document_version"),
                name="document_job_revision_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("bid_revision", "document_version"),
                name="document_job_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(document_version__gt=0),
                name="document_job_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(snapshot_schema_version__gt=0),
                name="document_job_schema_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="document_job_row_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=(
                            GenerationJobStatus.PENDING,
                            GenerationJobStatus.RUNNING,
                        ),
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        status=GenerationJobStatus.COMPLETED,
                        completed_at__isnull=False,
                        safe_error_code__isnull=True,
                    )
                    | models.Q(
                        status=GenerationJobStatus.FAILED,
                        completed_at__isnull=False,
                        safe_error_code__isnull=False,
                    )
                ),
                name="document_job_terminal_payload_valid",
            ),
        ]


class ImmutableFinalDocumentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Final Document tidak dapat diubah.")

    def delete(self):
        raise ValidationError("Final Document tidak dapat dihapus.")


class FinalDocument(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    generation_job = models.OneToOneField(
        DocumentGenerationJob,
        on_delete=models.PROTECT,
        related_name="final_document",
    )
    bid_revision = models.ForeignKey(
        "bids.BidProposalRevision",
        on_delete=models.PROTECT,
        related_name="final_documents",
    )
    document_version = models.PositiveIntegerField()
    document_number = models.CharField(max_length=100)
    template_version = models.CharField(max_length=32)
    object_key = models.CharField(max_length=512, unique=True)
    object_version_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    mime_type = models.CharField(
        max_length=100, default="application/pdf"
    )
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    snapshot_schema_version = models.PositiveIntegerField()
    content_snapshot = models.JSONField()
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finalized_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(
        ImmutableFinalDocumentQuerySet
    )()

    class Meta:
        db_table = "documents_final_document"
        ordering = ("-document_version", "-id")
        indexes = [
            models.Index(
                fields=("bid_revision", "-document_version"),
                name="final_document_revision_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("bid_revision", "document_version"),
                name="final_document_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(document_version__gt=0),
                name="final_document_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(size_bytes__gt=0),
                name="final_document_size_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(snapshot_schema_version__gt=0),
                name="final_document_schema_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(mime_type="application/pdf"),
                name="final_document_pdf_mime",
            ),
        ]

    def clean(self):
        super().clean()
        if self.generation_job_id and (
            self.generation_job.bid_revision_id
            != self.bid_revision_id
            or self.generation_job.document_version
            != self.document_version
        ):
            raise ValidationError(
                "Final Document tidak konsisten dengan generation job."
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Final Document tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Final Document tidak dapat dihapus.")
