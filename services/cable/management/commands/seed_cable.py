from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand

from core.providers.models import ProviderRoute
from services.cable.models import CablePackage, CablePackagePrice

# PLACEHOLDER names, codes and prices for development only.
# These are not current official prices. Enter real ones in the admin.
PACKAGES = {
    "dstv": [("Padi", "3000"), ("Yanga", "4200"), ("Confam", "7400"), ("Compact", "12500")],
    "gotv": [("Smallie", "1900"), ("Jinja", "3900"), ("Jolli", "5800"), ("Max", "8500")],
    "startimes": [("Nova", "1900"), ("Basic", "3700"), ("Smart", "5100")],
}


class Command(BaseCommand):
    help = "Dev only: create example cable packages and a mock provider route."

    def handle(self, *args, **options):
        for operator, items in PACKAGES.items():
            for order, (name, price) in enumerate(items):
                package, _ = CablePackage.objects.get_or_create(
                    operator=operator, name=name,
                    defaults={
                        "provider_code": f"{operator}-{name.lower()}",
                        "base_price": Decimal(price),
                        "sort_order": order,
                    },
                )
                reseller_price = (Decimal(price) * Decimal("0.98")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                CablePackagePrice.objects.get_or_create(
                    package=package, role="reseller",
                    defaults={"mode": "fixed", "value": reseller_price},
                )
        ProviderRoute.objects.get_or_create(
            service="cable", provider="mock", defaults={"priority": 10}
        )
        self.stdout.write(self.style.SUCCESS("Cable seed created."))