from decimal import Decimal

from django.conf import settings
from django.db import models


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="wallet"
    )
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0), name="wallet_balance_non_negative"
            )
        ]

    def __str__(self):
        return f"Wallet({self.user_id}) {self.balance}"


class LedgerEntry(models.Model):
    class Type(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries")
    entry_type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "reference", "entry_type"], name="uniq_wallet_ref_type"
            ),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ledger_amount_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError("Ledger entries are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Ledger entries cannot be deleted.")

class ManualFunding(models.Model):
    """Append-only record of an admin crediting a wallet by hand."""
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="manual_fundings")
    funded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="manualfunding_amount_positive"
            ),
        ]
        permissions = [
            ("fund_wallet", "Can manually fund user wallets"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError("Manual funding records cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Manual funding records cannot be deleted.")

    def __str__(self):
        return f"{self.wallet_id} +{self.amount} by {self.funded_by_id}"