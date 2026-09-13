from django.db import models


class OfferAuditAction(models.TextChoices):
    OFFER_CREATED = "OFFER_CREATED", "Offer created"
    OFFER_CORRECTED = "OFFER_CORRECTED", "Offer corrected"
    OFFER_SUPERSEDED = "OFFER_SUPERSEDED", "Offer superseded"
    OFFER_DEACTIVATED = "OFFER_DEACTIVATED", "Offer deactivated"
