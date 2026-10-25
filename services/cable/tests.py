import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.common.exceptions import ServiceError
from core.providers.models import ProviderRoute
from core.transactions.models import S, Transaction
from core.wallet.models import LedgerEntry
from core.wallet.services import credit

from .models import CablePackage, CablePackagePrice, SmartcardVerification
from .services import purchase, verify


class CableTestBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )
        self.other = User.objects.create_user(
            username="t2", email="t2@example.com", password="pass12345"
        )
        self.reseller = User.objects.create_user(
            username="r1", email="r1@example.com", password="pass12345", role="reseller"
        )
        credit(self.user, "20000", "fund-1")
        credit(self.reseller, "20000", "fund-2")
        self.package = CablePackage.objects.create(
            operator="dstv", name="Compact", validity="1 month",
            provider_code="dstv-compact", base_price="12500",
        )
        CablePackagePrice.objects.create(package=self.package, role="reseller", value="12000")
        self.gotv_package = CablePackage.objects.create(
            operator="gotv", name="Jinja", provider_code="gotv-jinja", base_price="3900"
        )
        ProviderRoute.objects.create(service="cable", provider="mock", priority=10)

    def balance(self, user):
        user.wallet.refresh_from_db()
        return user.wallet.balance

    def make_verification(self, user=None, card="1234567890", operator="dstv", expires_in=10):
        return SmartcardVerification.objects.create(
            user=user or self.user, operator=operator, smartcard=card,
            customer_name="JOHN DOE",
            expires_at=timezone.now() + timedelta(minutes=expires_in),
        )


class VerifyTests(CableTestBase):
    def test_verify_returns_customer_and_moves_no_money(self):
        v = verify(self.user, "dstv", "1234567890")
        self.assertEqual(v.customer_name, "MOCK CUSTOMER")
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(self.balance(self.user), Decimal("20000.00"))
        self.assertEqual(LedgerEntry.objects.filter(wallet=self.user.wallet).count(), 1)

    def test_unknown_smartcard(self):
        with self.assertRaises(ServiceError) as ctx:
            verify(self.user, "dstv", "1234560000")
        self.assertEqual(ctx.exception.code, "INVALID_SMARTCARD")

    def test_vendor_down_is_a_different_error(self):
        with self.assertRaises(ServiceError) as ctx:
            verify(self.user, "dstv", "1234569999")
        self.assertEqual(ctx.exception.code, "VERIFICATION_UNAVAILABLE")
        self.assertEqual(SmartcardVerification.objects.count(), 0)

    def test_bad_format(self):
        with self.assertRaises(ServiceError) as ctx:
            verify(self.user, "dstv", "12ab")
        self.assertEqual(ctx.exception.code, "INVALID_SMARTCARD")

    def test_bad_operator(self):
        with self.assertRaises(ServiceError) as ctx:
            verify(self.user, "sky", "1234567890")
        self.assertEqual(ctx.exception.code, "INVALID_OPERATOR")


class PurchaseTests(CableTestBase):
    def test_purchase_uses_the_verified_smartcard(self):
        v = self.make_verification()
        txn, created = purchase(self.user, v.pk, self.package.pk)
        self.assertTrue(created)
        self.assertEqual(txn.status, S.SUCCESS)
        self.assertEqual(txn.destination, "1234567890")
        self.assertEqual(txn.payload["customer_name"], "JOHN DOE")
        self.assertEqual(txn.payload["package_code"], "dstv-compact")
        self.assertEqual(self.balance(self.user), Decimal("7500.00"))

    def test_reseller_gets_their_price(self):
        v = self.make_verification(user=self.reseller)
        txn, _ = purchase(self.reseller, v.pk, self.package.pk)
        self.assertEqual(txn.amount, Decimal("12000.00"))
        self.assertEqual(self.balance(self.reseller), Decimal("8000.00"))

    def test_expired_verification_is_rejected(self):
        v = self.make_verification(expires_in=-1)
        with self.assertRaises(ServiceError) as ctx:
            purchase(self.user, v.pk, self.package.pk)
        self.assertEqual(ctx.exception.code, "VERIFICATION_EXPIRED")
        self.assertEqual(self.balance(self.user), Decimal("20000.00"))

    def test_someone_elses_verification_is_rejected(self):
        v = self.make_verification(user=self.other)
        with self.assertRaises(ServiceError) as ctx:
            purchase(self.user, v.pk, self.package.pk)
        self.assertEqual(ctx.exception.code, "INVALID_VERIFICATION")

    def test_unknown_verification_is_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            purchase(self.user, uuid.uuid4(), self.package.pk)
        self.assertEqual(ctx.exception.code, "INVALID_VERIFICATION")

    def test_package_must_match_the_operator(self):
        v = self.make_verification(operator="dstv")
        with self.assertRaises(ServiceError) as ctx:
            purchase(self.user, v.pk, self.gotv_package.pk)
        self.assertEqual(ctx.exception.code, "PACKAGE_MISMATCH")

    def test_account_changed_after_verification_refunds(self):
        # Valid when checked, rejected by the vendor at purchase time.
        v = self.make_verification(card="1234560000")
        txn, _ = purchase(self.user, v.pk, self.package.pk)
        self.assertEqual(txn.status, S.REFUNDED)
        self.assertEqual(self.balance(self.user), Decimal("20000.00"))

    def test_retry_after_expiry_returns_the_original_order(self):
        v = self.make_verification()
        first, _ = purchase(self.user, v.pk, self.package.pk, reference="ref-1")
        SmartcardVerification.objects.filter(pk=v.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        again, created = purchase(self.user, v.pk, self.package.pk, reference="ref-1")
        self.assertFalse(created)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(self.balance(self.user), Decimal("7500.00"))


class CableApiTests(CableTestBase):
    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_full_flow(self):
        client = self.client_for(self.user)
        verified = client.post(
            "/api/v1/cable/verify/",
            {"operator": "dstv", "smartcard": "1234567890"}, format="json",
        )
        self.assertEqual(verified.status_code, 200)
        bought = client.post(
            "/api/v1/cable/purchase/",
            {
                "verification_id": verified.data["verification_id"],
                "package_id": self.package.pk,
                "reference": "api-1",
            },
            format="json",
        )
        self.assertEqual(bought.status_code, 201)
        self.assertEqual(bought.data["status"], "success")
        self.assertEqual(bought.data["customer_name"], "MOCK CUSTOMER")
        status = client.get("/api/v1/cable/orders/api-1/")
        self.assertEqual(status.status_code, 200)

    def test_requires_login(self):
        response = APIClient().post("/api/v1/cable/verify/", {}, format="json")
        self.assertIn(response.status_code, (401, 403))

    def test_vendor_down_returns_503(self):
        response = self.client_for(self.user).post(
            "/api/v1/cable/verify/",
            {"operator": "dstv", "smartcard": "1234569999"}, format="json",
        )
        self.assertEqual(response.status_code, 503)

    def test_packages_show_role_price(self):
        response = self.client_for(self.reseller).get("/api/v1/cable/packages/?operator=dstv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["price"], "12000.00")