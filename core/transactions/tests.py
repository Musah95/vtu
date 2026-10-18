from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.wallet.models import LedgerEntry
from core.wallet.services import credit

from .models import Transaction
from .services import InvalidTransition, initiate, mark_failed, mark_success

S = Transaction.Status


class TransactionFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )
        credit(self.user, "1000", "fund-1")

    def balance(self):
        self.user.wallet.refresh_from_db()
        return self.user.wallet.balance

    def test_success_path(self):
        txn, created = initiate(self.user, "airtime", "300", reference="r1", destination="08012345678")
        self.assertTrue(created)
        self.assertEqual(txn.status, S.PROCESSING)
        self.assertEqual(self.balance(), Decimal("700.00"))
        txn = mark_success(txn.pk, provider="mock", provider_reference="p1")
        self.assertEqual(txn.status, S.SUCCESS)
        self.assertEqual(self.balance(), Decimal("700.00"))

    def test_failure_refunds(self):
        txn, _ = initiate(self.user, "airtime", "300", reference="r1")
        txn = mark_failed(txn.pk, "provider rejected")
        self.assertEqual(txn.status, S.REFUNDED)
        self.assertEqual(self.balance(), Decimal("1000.00"))
        self.assertEqual(LedgerEntry.objects.filter(wallet=self.user.wallet).count(), 3)

    def test_refund_happens_once(self):
        txn, _ = initiate(self.user, "airtime", "300", reference="r1")
        mark_failed(txn.pk, "x")
        mark_failed(txn.pk, "x")
        self.assertEqual(self.balance(), Decimal("1000.00"))

    def test_duplicate_reference_does_not_double_debit(self):
        initiate(self.user, "airtime", "300", reference="r1")
        txn, created = initiate(self.user, "airtime", "300", reference="r1")
        self.assertFalse(created)
        self.assertEqual(self.balance(), Decimal("700.00"))

    def test_insufficient_balance_fails_cleanly(self):
        txn, created = initiate(self.user, "airtime", "5000", reference="r2")
        self.assertTrue(created)
        self.assertEqual(txn.status, S.FAILED)
        self.assertEqual(self.balance(), Decimal("1000.00"))

    def test_successful_transaction_cannot_be_failed(self):
        txn, _ = initiate(self.user, "airtime", "300", reference="r1")
        mark_success(txn.pk)
        with self.assertRaises(InvalidTransition):
            mark_failed(txn.pk, "late failure")