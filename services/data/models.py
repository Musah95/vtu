from django.db import models

from core.accounts.models import User


class Network(models.TextChoices):
    MTN = "mtn", "MTN"
    AIRTEL = "airtel", "Airtel"
    GLO = "glo", "Glo"
    NINE_MOBILE = "9mobile", "9mobile"


class DataPlan(models.Model):
    network = models.CharField(max_length=20, choices=Network.choices, db_index=True)
    category = models.CharField(max_length=30, blank=True)       # "SME", "Gifting", ...
    name = models.CharField(max_length=100)                      # "1GB"
    validity = models.CharField(max_length=50, blank=True)       # "30 days"
    provider_code = models.CharField(max_length=50)              # the vendor's plan id
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["network", "sort_order", "base_price"]
        constraints = [
            models.UniqueConstraint(
                fields=["network", "category", "name"], name="uniq_data_plan"
            )
        ]

    def __str__(self):
        return f"{self.get_network_display()} {self.category} {self.name} ({self.validity})"


class DataPlanPrice(models.Model):
    """Optional price override for one user role. No row means base_price applies."""
    plan = models.ForeignKey(DataPlan, on_delete=models.CASCADE, related_name="prices")
    role = models.CharField(max_length=20, choices=User.Role.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "role"], name="uniq_dataplan_role")
        ]

    def __str__(self):
        return f"{self.plan} / {self.role}: {self.price}"