from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.wallet"
    label = "wallet"

    def ready(self):
        from . import signals  # noqa: F401