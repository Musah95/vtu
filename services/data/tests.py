from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.common.exceptions import ServiceError
from core.providers.models import ProviderRoute
from core.transactions.models import S
from core.wallet.services import credit

from .models import DataPlan, DataPlanPrice
from .services import purchase


class DataTestBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )
        self.reseller = User.objects.create_user(
            username="r1", email="r1@example.com", password="pass12345", role="reseller"
        )
        credit(self.user, "5000", "fund-1")
        credit(self.reseller, "5000", "fund-2")
        self.plan = DataPlan.objects.create(
            network="mtn", category="SME", name="1GB", validity="30 days",
            provider_code="mtn-1gb", base_price="290",
        )
        DataPlanPrice.objects.create(plan=self.plan, role="reseller", value="270")
        ProviderRoute.objects.create(service="data", provider="mock", priority=10)

    def balance(self, user):
        user.wallet.refresh_from_db()
        return user.wallet.balance


class DataServiceTests(DataTestBase):
    def test_customer_pays_base_price(self):
        txn, created = purchase(self.user, self.plan.pk, "08012345678")
        self.assertTrue(created)
        self.assertEqual(txn.status, S.SUCCESS)
        self.assertEqual(txn.amount, Decimal("290.00"))
        self.assertEqual(txn.payload["plan_code"], "mtn-1gb")
        self.assertEqual(self.balance(self.user), Decimal("4710.00"))

    def test_reseller_gets_override_price(self):
        txn, _ = purchase(self.reseller, self.plan.pk, "08012345678")
        self.assertEqual(txn.amount, Decimal("270.00"))
        self.assertEqual(self.balance(self.reseller), Decimal("4730.00"))

    def test_inactive_plan_is_rejected(self):
        self.plan.is_active = False
        self.plan.save()
        with self.assertRaises(ServiceError) as ctx:
            purchase(self.user, self.plan.pk, "08012345678")
        self.assertEqual(ctx.exception.code, "INVALID_PLAN")

    def test_invalid_phone_is_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            purchase(self.user, self.plan.pk, "12345")
        self.assertEqual(ctx.exception.code, "INVALID_NUMBER")

    def test_duplicate_reference_charges_once(self):
        purchase(self.user, self.plan.pk, "08012345678", reference="ref-1")
        _, created = purchase(self.user, self.plan.pk, "08012345678", reference="ref-1")
        self.assertFalse(created)
        self.assertEqual(self.balance(self.user), Decimal("4710.00"))

    def test_provider_rejection_refunds(self):
        txn, _ = purchase(self.user, self.plan.pk, "08012340000")
        self.assertEqual(txn.status, S.REFUNDED)
        self.assertEqual(self.balance(self.user), Decimal("5000.00"))

    def test_insufficient_balance(self):
        poor = get_user_model().objects.create_user(
            username="poor", email="poor@example.com", password="pass12345"
        )
        txn, _ = purchase(poor, self.plan.pk, "08012345678")
        self.assertEqual(txn.status, S.FAILED)
        self.assertEqual(self.balance(poor), Decimal("0.00"))


class DataApiTests(DataTestBase):
    def test_plans_show_role_specific_price(self):
        client = APIClient()
        client.force_authenticate(self.reseller)
        response = client.get("/api/v1/data/plans/?network=mtn")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["price"], "270.00")

    def test_purchase_success(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            "/api/v1/data/purchase/",
            {"plan_id": self.plan.pk, "phone": "08012345678"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "success")

    def test_requires_login(self):
        response = APIClient().get("/api/v1/data/plans/")
        self.assertIn(response.status_code, (401, 403))