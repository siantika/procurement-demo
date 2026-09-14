from django.db import models


class SignatureAuditAction(models.TextChoices):
    SIGNED = "BID_SIGNED", "Bid signed"
