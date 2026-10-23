from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand

from core.providers.models import ProviderRoute
from services.data.models import DataPlan, DataPlanPrice

NETWORKS = ["mtn", "airtel", "glo", "9mobile"]
# Placeholder sizes, prices and vendor codes for development only.
# Enter your real plans and prices in the admin.
SIZES = [("500MB", "150"), ("1GB", "290"), ("2GB", "580")]


class Command(BaseCommand):
    help = "Dev only: create example data plans and a mock provider route."

    def handle(self, *args, **options):
        for network in NETWORKS:
            for order, (size, price) in enumerate(SIZES):
                plan, _ = DataPlan.objects.get_or_create(
                    network=network, category="SME", name=size,
                    defaults={
                        "validity": "30 days",
                        "provider_code": f"{network}-{size.lower()}",
                        "base_price": Decimal(price),
                        "sort_order": order,
                    },
                )
                reseller_price = (Decimal(price) * Decimal("0.95")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                DataPlanPrice.objects.get_or_create(
                    plan=plan, role="reseller", defaults={"price": reseller_price}
                )
        ProviderRoute.objects.get_or_create(
            service="data", provider="mock", defaults={"priority": 10}
        )
        self.stdout.write(self.style.SUCCESS("Data seed created."))