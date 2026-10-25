import uuid

from django.conf import settings
from django.db import models

from core.pricing.models import PriceRuleBase


class Operator(models.TextChoices):
    DSTV = "dstv", "DStv"
    GOTV = "gotv", "GOtv"
    STARTIMES = "startimes", "StarTimes"


class CablePackage(models.Model):
    operator = models.CharField(max_length=20, choices=Operator.choices, db_index=True)
    name = models.CharField(max_length=100)                       # "Compact"
    validity = models.CharField(max_length=50, blank=True, default="1 month")
    provider_code = models.CharField(max_length=50)               # the vendor's package id
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["operator", "sort_order", "base_price"]
        constraints = [
            models.UniqueConstraint(fields=["operator", "name"], name="uniq_cable_package")
        ]

    def __str__(self):
        return f"{self.get_operator_display()} {self.name} ({self.validity})"


class CablePackagePrice(PriceRuleBase):
    """Optional price rule for one user role. No row means base_price applies."""
    mode = models.CharField(
        max_length=20, choices=PriceRuleBase.Mode.choices, default=PriceRuleBase.Mode.FIXED
    )
    package = models.ForeignKey(CablePackage, on_delete=models.CASCADE, related_name="prices")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["package", "role"], name="uniq_cablepackage_role")
        ]

    def __str__(self):
        return f"{self.package} / {self.role}: {self.mode} {self.value}"


class SmartcardVerification(models.Model):
    """A vendor-confirmed smartcard, usable for a short time by the user who checked it."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # the token
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    operator = models.CharField(max_length=20, choices=Operator.choices)
    smartcard = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=150, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.operator} {self.smartcard} ({self.customer_name})"