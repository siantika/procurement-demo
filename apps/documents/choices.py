from django.db import models


class GenerationJobStatus(models.TextChoices):
    PENDING = "PENDING", "Menunggu"
    RUNNING = "RUNNING", "Diproses"
    COMPLETED = "COMPLETED", "Selesai"
    FAILED = "FAILED", "Gagal"


class DocumentAuditAction(models.TextChoices):
    REQUESTED = (
        "DOCUMENT_GENERATION_REQUESTED",
        "Document generation requested",
    )
    FINALIZED = "DOCUMENT_FINALIZED", "Document finalized"
    FAILED = (
        "DOCUMENT_GENERATION_FAILED",
        "Document generation failed",
    )
