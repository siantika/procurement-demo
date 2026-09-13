from django.db import models


class OfferAuditAction(models.TextChoices):
    OFFER_CREATED = "OFFER_CREATED", "Offer created"
    OFFER_CORRECTED = "OFFER_CORRECTED", "Offer corrected"
    OFFER_SUPERSEDED = "OFFER_SUPERSEDED", "Offer superseded"
    OFFER_DEACTIVATED = "OFFER_DEACTIVATED", "Offer deactivated"


class ResultSourceType(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    OPTIMIZER = "OPTIMIZER", "Optimizer"
    CUSTOMIZED = "CUSTOMIZED", "Customized"


class ResultStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    VALID = "VALID", "Valid"


class ResultAuditAction(models.TextChoices):
    RESULT_CREATED = "RESULT_CREATED", "Result created"
    RESULT_UPDATED = "RESULT_UPDATED", "Result updated"
    RESULT_VALIDATED = "RESULT_VALIDATED", "Result validated"
    RESULT_CUSTOMIZED = "RESULT_CUSTOMIZED", "Result customized"
    RESULT_SELECTED = "RESULT_SELECTED", "Result selected"
