from django.db import models


class CatalogAuditAction(models.TextChoices):
    PRODUCT_CREATED = "PRODUCT_CREATED", "Product created"
    PRODUCT_UPDATED = "PRODUCT_UPDATED", "Product updated"
    PRODUCT_DEACTIVATED = "PRODUCT_DEACTIVATED", "Product deactivated"
    PRODUCT_REACTIVATED = "PRODUCT_REACTIVATED", "Product reactivated"
    SUPPLIER_CREATED = "SUPPLIER_CREATED", "Supplier created"
    SUPPLIER_UPDATED = "SUPPLIER_UPDATED", "Supplier updated"
    SUPPLIER_DEACTIVATED = "SUPPLIER_DEACTIVATED", "Supplier deactivated"
