# Create your tests here.
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .services import InsufficientBalance, credit, debit


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