from django.db import models


class BidStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    WAITING_APPROVAL = "WAITING_APPROVAL", "Menunggu approval"
    APPROVED = "APPROVED", "Disetujui"
    REJECTED = "REJECTED", "Ditolak"
    SIGNED = "SIGNED", "Ditandatangani"
    FINALIZED = "FINALIZED", "Final"


class BidAuditAction(models.TextChoices):
    CREATED = "BID_CREATED", "Bid created"
    PRICED = "BID_PRICED", "Bid priced"
    SUBMITTED = "BID_SUBMITTED", "Bid submitted"
    REVISION_CREATED = "BID_REVISION_CREATED", "Bid revision created"
