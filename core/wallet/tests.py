# Create your tests here.
from django.contrib.auth.models import Permission

from .models import LedgerEntry, ManualFunding, Wallet
from .services import ManualFundingError, fund_manually

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .services import InsufficientBalance, credit, debit
from rest_framework.test import APIClient

class WalletServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )

    def test_credit_and_debit(self):
        credit(self.user, "1000", "fund-1")
        debit(self.user, "300", "buy-1")
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, Decimal("700.00"))

    def test_debit_is_idempotent(self):
        credit(self.user, "1000", "fund-1")
        debit(self.user, "300", "buy-1")
        debit(self.user, "300", "buy-1")
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, Decimal("700.00"))

    def test_cannot_overdraw(self):
        credit(self.user, "100", "fund-1")
        with self.assertRaises(InsufficientBalance):
            debit(self.user, "500", "buy-1")

class BalanceEndpointTests(TestCase):
    def test_balance(self):
        user = get_user_model().objects.create_user(
            username="t9", email="t9@example.com", password="pass12345"
        )
        credit(user, "5000", "fund-1")
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/v1/wallet/balance/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], "5000.00")

class ManualFundingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="cust", email="cust@example.com", password="pass12345"
        )
        self.staff = User.objects.create_user(
            username="clerk", email="clerk@example.com", password="pass12345", is_staff=True
        )
        self.admin = User.objects.create_superuser(
            username="boss", email="boss@example.com", password="pass12345"
        )

    def balance(self, user=None):
        user = user or self.user
        user.wallet.refresh_from_db()
        return user.wallet.balance

    def test_funding_credits_and_records(self):
        record = fund_manually(self.user, "5000", self.admin, "bank ref 123456")
        self.assertEqual(self.balance(), Decimal("5000.00"))
        self.assertEqual(ManualFunding.objects.count(), 1)
        entry = LedgerEntry.objects.get(
            wallet=self.user.wallet, reference=f"manual-fund:{record.pk}"
        )
        self.assertEqual(entry.amount, Decimal("5000.00"))

    def test_note_is_required(self):
        with self.assertRaises(ManualFundingError):
            fund_manually(self.user, "5000", self.admin, "   ")
        self.assertEqual(self.balance(), Decimal("0.00"))
        self.assertEqual(ManualFunding.objects.count(), 0)

    def test_amount_must_be_a_positive_number(self):
        for bad in ("0", "-5", "abc"):
            with self.assertRaises(ManualFundingError):
                fund_manually(self.user, bad, self.admin, "note")
        self.assertEqual(self.balance(), Decimal("0.00"))

    def test_amount_over_the_limit_is_rejected(self):
        with self.assertRaises(ManualFundingError):
            fund_manually(self.user, "500000.01", self.admin, "typo?")
        self.assertEqual(self.balance(), Decimal("0.00"))

    def test_staff_cannot_fund_their_own_wallet(self):
        with self.assertRaises(ManualFundingError):
            fund_manually(self.staff, "100", self.staff, "self funding")
        self.assertEqual(self.balance(self.staff), Decimal("0.00"))

    def test_superuser_may_fund_their_own_wallet(self):
        fund_manually(self.admin, "100", self.admin, "staging test money")
        self.assertEqual(self.balance(self.admin), Decimal("100.00"))

    def test_records_are_append_only(self):
        record = fund_manually(self.user, "100", self.admin, "first")
        record.note = "edited"
        with self.assertRaises(RuntimeError):
            record.save()

    def test_admin_action_funds_the_wallet(self):
        self.client.force_login(self.admin)
        self.client.post(
            "/admin/wallet/wallet/",
            {
                "action": "credit_wallet",
                "_selected_action": [self.user.wallet.pk],
                "amount": "2500",
                "note": "bank ref 987654",
                "index": 0,
            },
            follow=True,
        )
        self.assertEqual(self.balance(), Decimal("2500.00"))

    def test_admin_action_with_a_bad_amount_changes_nothing(self):
        self.client.force_login(self.admin)
        self.client.post(
            "/admin/wallet/wallet/",
            {
                "action": "credit_wallet",
                "_selected_action": [self.user.wallet.pk],
                "amount": "abc",
                "note": "bank ref",
                "index": 0,
            },
            follow=True,
        )
        self.assertEqual(self.balance(), Decimal("0.00"))

    def test_staff_without_the_permission_cannot_fund(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_wallet"))
        self.client.force_login(self.staff)
        self.client.post(
            "/admin/wallet/wallet/",
            {
                "action": "credit_wallet",
                "_selected_action": [self.user.wallet.pk],
                "amount": "2500",
                "note": "bank ref",
                "index": 0,
            },
            follow=True,
        )
        self.assertEqual(self.balance(), Decimal("0.00"))