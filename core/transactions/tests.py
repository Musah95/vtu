from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.wallet.models import LedgerEntry
from core.wallet.services import credit

from .models import Transaction
from .services import InvalidTransition, initiate, mark_failed, mark_success

from datetime import timedelta

from django.utils import timezone

from .models import ManualResolution
from .services import ManualResolutionError, resolve_manually

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

class ManualResolutionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )
        self.admin = User.objects.create_superuser(
            username="boss", email="boss@example.com", password="pass12345"
        )
        credit(self.user, "1000", "fund-1")

    def stuck_txn(self, ref="r1", age_minutes=5):
        txn, _ = initiate(self.user, "airtime", "300", reference=ref)
        Transaction.objects.filter(pk=txn.pk).update(
            updated_at=timezone.now() - timedelta(minutes=age_minutes)
        )
        return txn

    def balance(self):
        self.user.wallet.refresh_from_db()
        return self.user.wallet.balance

    def test_manual_fail_refunds_and_records(self):
        txn = self.stuck_txn()
        result = resolve_manually(txn.pk, "failed", self.admin, "vendor confirmed not delivered")
        self.assertEqual(result.status, S.REFUNDED)
        self.assertEqual(self.balance(), Decimal("1000.00"))
        record = ManualResolution.objects.get()
        self.assertEqual(record.resolved_by, self.admin)
        self.assertEqual(record.outcome, "failed")

    def test_manual_success_keeps_the_debit(self):
        txn = self.stuck_txn()
        result = resolve_manually(txn.pk, "success", self.admin, "vendor dashboard shows delivered")
        self.assertEqual(result.status, S.SUCCESS)
        self.assertEqual(self.balance(), Decimal("700.00"))

    def test_note_is_required(self):
        txn = self.stuck_txn()
        with self.assertRaises(ManualResolutionError):
            resolve_manually(txn.pk, "failed", self.admin, "   ")
        txn.refresh_from_db()
        self.assertEqual(txn.status, S.PROCESSING)
        self.assertEqual(ManualResolution.objects.count(), 0)

    def test_recent_order_is_rejected(self):
        txn = self.stuck_txn(age_minutes=0)
        with self.assertRaises(ManualResolutionError):
            resolve_manually(txn.pk, "failed", self.admin, "too early")
        self.assertEqual(self.balance(), Decimal("700.00"))

    def test_only_processing_orders_can_be_resolved(self):
        txn = self.stuck_txn()
        mark_success(txn.pk)
        with self.assertRaises(ManualResolutionError):
            resolve_manually(txn.pk, "failed", self.admin, "should not refund a success")
        self.assertEqual(self.balance(), Decimal("700.00"))

    def test_cannot_refund_twice(self):
        txn = self.stuck_txn()
        resolve_manually(txn.pk, "failed", self.admin, "first")
        with self.assertRaises(ManualResolutionError):
            resolve_manually(txn.pk, "failed", self.admin, "second")
        self.assertEqual(self.balance(), Decimal("1000.00"))

    def test_records_are_append_only(self):
        txn = self.stuck_txn()
        resolve_manually(txn.pk, "failed", self.admin, "first")
        record = ManualResolution.objects.get()
        record.note = "edited"
        with self.assertRaises(RuntimeError):
            record.save()

    def test_admin_action_refunds(self):
        txn = self.stuck_txn()
        self.client.force_login(self.admin)
        self.client.post(
            "/admin/transactions/transaction/",
            {
                "action": "mark_failed_and_refund",
                "_selected_action": [txn.pk],
                "note": "vendor confirmed not delivered",
                "index": 0,
            },
            follow=True,
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, S.REFUNDED)

    def test_admin_action_without_note_changes_nothing(self):
        txn = self.stuck_txn()
        self.client.force_login(self.admin)
        self.client.post(
            "/admin/transactions/transaction/",
            {
                "action": "mark_failed_and_refund",
                "_selected_action": [txn.pk],
                "note": "",
                "index": 0,
            },
            follow=True,
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, S.PROCESSING)