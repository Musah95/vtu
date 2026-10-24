from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from core.accounts.models import User


class PriceRuleBase(models.Model):
    class Mode(models.TextChoices):
        FIXED = "fixed", "Fixed price"
        PERCENT_OFF = "percent_off", "Percent off"

    # Subclasses narrow this to the modes that make sense for them.
    allowed_modes = (Mode.FIXED, Mode.PERCENT_OFF)

    role = models.CharField(max_length=20, choices=User.Role.choices)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.PERCENT_OFF)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.mode not in self.allowed_modes:
            raise ValidationError({"mode": "This mode isn't allowed for this kind of rule."})
        if self.mode == self.Mode.FIXED and self.value <= 0:
            raise ValidationError({"value": "A fixed price must be greater than zero."})
        if self.mode == self.Mode.PERCENT_OFF and not (0 <= self.value < 100):
            raise ValidationError({"value": "Percent off must be at least 0 and below 100."})