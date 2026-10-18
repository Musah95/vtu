from django.apps import AppConfig


class ProvidersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.providers"
    label = "providers"

    def ready(self):
        from .adapters import mock  # noqa: F401  (registers the mock adapter)