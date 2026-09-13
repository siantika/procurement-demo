from django.db import models


class NotificationType(models.TextChoices):
    OPTIMIZATION_COMPLETED = (
        "OPTIMIZATION_COMPLETED",
        "Optimization selesai",
    )
    OPTIMIZATION_FAILED = "OPTIMIZATION_FAILED", "Optimization gagal"
    BID_REJECTED = "BID_REJECTED", "Bid ditolak"
