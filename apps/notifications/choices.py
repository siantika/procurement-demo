from django.db import models


class NotificationType(models.TextChoices):
    BID_WAITING_APPROVAL = (
        "BID_WAITING_APPROVAL",
        "Bid menunggu approval",
    )
    OPTIMIZATION_COMPLETED = (
        "OPTIMIZATION_COMPLETED",
        "Optimization selesai",
    )
    OPTIMIZATION_FAILED = "OPTIMIZATION_FAILED", "Optimization gagal"
    BID_REJECTED = "BID_REJECTED", "Bid ditolak"
    DOCUMENT_COMPLETED = "DOCUMENT_COMPLETED", "Dokumen selesai"
    DOCUMENT_FAILED = "DOCUMENT_FAILED", "Dokumen gagal"
