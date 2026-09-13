from django.db import models


class OptimizationStatus(models.TextChoices):
    PENDING = "PENDING", "Menunggu"
    RUNNING = "RUNNING", "Berjalan"
    COMPLETED = "COMPLETED", "Selesai"
    FAILED = "FAILED", "Gagal"


class OptimizationAuditAction(models.TextChoices):
    REQUESTED = "OPTIMIZATION_REQUESTED", "Optimization requested"
    STARTED = "OPTIMIZATION_STARTED", "Optimization started"
    COMPLETED = "OPTIMIZATION_COMPLETED", "Optimization completed"
    FAILED = "OPTIMIZATION_FAILED", "Optimization failed"
