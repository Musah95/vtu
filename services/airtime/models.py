from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.accounts.models import User


class Network(models.Model):
    code = models.SlugField(max_length=20, unique=True)      # "mtn", "airtel", ...
    name = models.CharField(max_length=50)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("50.00"))
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("50000.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AirtimePricing(models.Model):
    """Discount a given user role gets on a network (0 = pays full face value)."""
    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="pricing")
    role = models.CharField(max_length=20, choices=User.Role.choices)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["network", "role"], name="uniq_airtime_network_role")
        ]

    def __str__(self):
        return f"{self.network.code} / {self.role}: {self.discount_percent}%"