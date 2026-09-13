from django.db import models


class ApprovalDecisionType(models.TextChoices):
    APPROVED = "APPROVED", "Disetujui"
    REJECTED = "REJECTED", "Ditolak"


class ApprovalAuditAction(models.TextChoices):
    APPROVED = "BID_APPROVED", "Bid approved"
    REJECTED = "BID_REJECTED", "Bid rejected"
