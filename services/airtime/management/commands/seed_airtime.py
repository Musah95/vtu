from decimal import Decimal

from django.core.management.base import BaseCommand

from core.providers.models import ProviderRoute
from services.airtime.models import AirtimePricing, Network

NETWORKS = [("mtn", "MTN"), ("airtel", "Airtel"), ("glo", "Glo"), ("9mobile", "9mobile")]
# Placeholder discounts for development. Set your real ones in the admin.
DISCOUNTS = {"customer": "1.50", "agent": "2.50", "reseller": "3.50"}


class Command(BaseCommand):
    help = "Dev only: create networks, example discounts, and a mock provider route."

    def handle(self, *args, **options):
        for code, name in NETWORKS:
            network, _ = Network.objects.get_or_create(code=code, defaults={"name": name})
            for role, pct in DISCOUNTS.items():
                AirtimePricing.objects.get_or_create(
                    network=network, role=role,
                    defaults={"mode": "percent_off", "value": Decimal(pct)},
                )
        ProviderRoute.objects.get_or_create(
            service="airtime", provider="mock", defaults={"priority": 10}
        )
        self.stdout.write(self.style.SUCCESS("Airtime seed data created."))