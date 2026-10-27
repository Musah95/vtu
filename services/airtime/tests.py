from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.providers.models import ProviderRoute
from core.transactions.models import S
from core.wallet.services import credit

from .models import AirtimePricing, Network
from .services import AirtimeError, normalize_phone, purchase
from django.core.exceptions import ValidationError

from core.apikeys.services import create_key
from core.transactions.models import Transaction

class AirtimeTestBase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )
        credit(self.user, "5000", "fund-1")
        net = Network.objects.create(code="mtn", name="MTN")
        AirtimePricing.objects.create(network=net, role="customer", mode="percent_off", value="2.00")
        ProviderRoute.objects.create(service="airtime", provider="mock", priority=10)

    def balance(self, user=None):
        user = user or self.user
        user.wallet.refresh_from_db()
        return user.wallet.balance


class AirtimeServiceTests(AirtimeTestBase):
    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+234 801 234 5678"), "08012345678")
        with self.assertRaises(AirtimeError):
            normalize_phone("12345")

    def test_discount_is_applied(self):
        txn, _ = purchase(self.user, "mtn", "08012345678", "1000")
        self.assertEqual(txn.amount, Decimal("980.00"))
        self.assertEqual(self.balance(), Decimal("4020.00"))

    def test_purchase_success(self):
        txn, created = purchase(self.user, "mtn", "08012345678", "1000")
        self.assertTrue(created)
        self.assertEqual(txn.status, S.SUCCESS)
        self.assertEqual(txn.payload["face_value"], "1000.00")

    def test_duplicate_reference_charges_once(self):
        purchase(self.user, "mtn", "08012345678", "1000", reference="ref-1")
        _, created = purchase(self.user, "mtn", "08012345678", "1000", reference="ref-1")
        self.assertFalse(created)
        self.assertEqual(self.balance(), Decimal("4020.00"))

    def test_amount_below_minimum(self):
        with self.assertRaises(AirtimeError) as ctx:
            purchase(self.user, "mtn", "08012345678", "10")
        self.assertEqual(ctx.exception.code, "INVALID_AMOUNT")

    def test_insufficient_balance(self):
        txn, _ = purchase(self.user, "mtn", "08012345678", "50000")
        self.assertEqual(txn.status, S.FAILED)
        self.assertEqual(self.balance(), Decimal("5000.00"))

    def test_fixed_rule_is_not_allowed_on_airtime(self):
        rule = AirtimePricing(network=Network.objects.get(code="mtn"), role="agent",
                              mode="fixed", value="500")
        with self.assertRaises(ValidationError):
            rule.full_clean()

class AirtimeApiTests(AirtimeTestBase):
    url = "/api/v1/airtime/purchase/"
    body = {"network": "mtn", "phone": "08012345678", "amount": "1000"}

    def test_requires_login(self):
        response = APIClient().post(self.url, self.body, format="json")
        self.assertIn(response.status_code, (401, 403))

    def test_purchase_success(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(self.url, self.body, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "success")

    def test_insufficient_balance_returns_402(self):
        poor = get_user_model().objects.create_user(
            username="poor", email="poor@example.com", password="pass12345"
        )
        client = APIClient()
        client.force_authenticate(poor)
        response = client.post(self.url, self.body, format="json")
        self.assertEqual(response.status_code, 402)

    def test_api_key_order_records_its_source(self):
        key, secret = create_key(self.user, "prod")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Key {key.key_id}:{secret}")
        response = client.post(self.url, {**self.body, "reference": "k-1"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Transaction.objects.get(reference="k-1").source, f"api:{key.key_id}")

    def test_session_order_records_web_source(self):
        client = APIClient()
        client.force_authenticate(self.user)
        client.post(self.url, {**self.body, "reference": "w-1"}, format="json")
        self.assertEqual(Transaction.objects.get(reference="w-1").source, "web")

    def test_repeated_reference_returns_the_original_order(self):
        client = APIClient()
        client.force_authenticate(self.user)
        first = client.post(self.url, {**self.body, "reference": "dup-1"}, format="json")
        again = client.post(self.url, {**self.body, "reference": "dup-1"}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data["reference"], "dup-1")
        self.assertEqual(self.balance(), Decimal("4020.00"))