from django.db import models


class TenderAuditAction(models.TextChoices):
    TENDER_CREATED = "TENDER_CREATED", "Tender created"
    TENDER_REVISED = "TENDER_REVISED", "Tender revised"
