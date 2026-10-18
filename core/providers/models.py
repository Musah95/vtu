from django.db import models


class ProviderRoute(models.Model):
    service = models.CharField(max_length=30, db_index=True)   # "airtime", "data", ...
    provider = models.CharField(max_length=50)                 # adapter name
    priority = models.PositiveSmallIntegerField(default=10)    # lowest number is tried first
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["service", "priority"]
        constraints = [
            models.UniqueConstraint(fields=["service", "provider"], name="uniq_service_provider")
        ]

    def __str__(self):
        return f"{self.service} -> {self.provider} (priority {self.priority})"