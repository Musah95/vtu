from django.conf import settings
from django.db import models


class ApiKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="api_keys"
    )
    label = models.CharField(max_length=100, blank=True)          # "production", "staging"
    key_id = models.CharField(max_length=40, unique=True, editable=False)
    secret_hash = models.CharField(max_length=64, editable=False)  # the secret itself is never stored
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        return f"{self.key_id} ({self.label or self.user_id})"