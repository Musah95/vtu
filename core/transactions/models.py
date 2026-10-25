from django.conf import settings
from django.db import models


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions"
    )
    service = models.CharField(max_length=30, db_index=True)   # "airtime", "data", ...
    reference = models.CharField(max_length=100)               # idempotency key, unique per user
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)

    amount = models.DecimalField(max_digits=14, decimal_places=2)       # what the user paid
    cost_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    destination = models.CharField(max_length=50, blank=True)           # phone, smartcard, meter...

    provider = models.CharField(max_length=50, blank=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict, blank=True)                # service-specific details
    provider_response = models.JSONField(default=dict, blank=True)      # raw response, for disputes
    failure_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "reference"], name="uniq_user_reference"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="txn_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.service} {self.reference} [{self.status}]"


S = Transaction.Status

ALLOWED_TRANSITIONS = {
    S.PENDING: {S.PROCESSING, S.FAILED},
    S.PROCESSING: {S.SUCCESS, S.FAILED},
    S.FAILED: {S.REFUNDED},
    S.SUCCESS: set(),
    S.REFUNDED: set(),
}

class ManualResolution(models.Model):
    """Append-only record of a human settling a stuck transaction."""

    class Outcome(models.TextChoices):
        FAILED = "failed", "Marked failed (refunded)"
        SUCCESS = "success", "Marked successful"

    transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name="manual_resolutions"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    note = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("resolve_transaction", "Can manually resolve stuck transactions"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError("Manual resolution records cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Manual resolution records cannot be deleted.")

    def __str__(self):
        return f"{self.transaction_id} {self.outcome} by {self.resolved_by_id}"