from datetime import timedelta

from django.utils import timezone

from core.transactions.models import Transaction

from .tasks import sweep_stuck_transactions

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.transactions.models import S
from core.transactions.services import initiate
from core.wallet.services import credit

from .base import ProviderAdapter, ProviderResult, ProviderStatus
from .dispatch import execute_purchase, requery
from .models import ProviderRoute
from .registry import register


@register
class AlwaysFail(ProviderAdapter):
    name = "always_fail"

    def purchase(self, request):
        return ProviderResult(ProviderStatus.FAILED, message="rejected")

    def requery(self, request_id):
        return ProviderResult(ProviderStatus.FAILED)


@register
class Crashy(ProviderAdapter):
    name = "crashy"

    def purchase(self, request):
        raise TimeoutError("boom")

    def requery(self, request_id):
        return ProviderResult(ProviderStatus.UNKNOWN)


class DispatchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="t1", email="t1@example.com", password="pass12345"
        )
        credit(self.user, "1000", "fund-1")
        ProviderRoute.objects.create(service="airtime", provider="mock", priority=10)

    def balance(self):
        self.user.wallet.refresh_from_db()
        return self.user.wallet.balance

    def buy(self, phone, ref):
        txn, _ = initiate(self.user, "airtime", "300", reference=ref, destination=phone)
        return execute_purchase(txn.pk)

    def test_success(self):
        txn = self.buy("08012345678", "r1")
        self.assertEqual(txn.status, S.SUCCESS)
        self.assertEqual(txn.provider, "mock")
        self.assertEqual(self.balance(), 700)

    def test_definitive_failure_refunds(self):
        txn = self.buy("08012340000", "r2")
        self.assertEqual(txn.status, S.REFUNDED)
        self.assertEqual(self.balance(), 1000)

    def test_timeout_stays_processing_then_requery_succeeds(self):
        txn = self.buy("08012349999", "r3")
        self.assertEqual(txn.status, S.PROCESSING)
        self.assertEqual(self.balance(), 700)      # not refunded
        txn = requery(txn.pk)
        self.assertEqual(txn.status, S.SUCCESS)

    def test_fallback_after_definitive_failure(self):
        ProviderRoute.objects.create(service="airtime", provider="always_fail", priority=1)
        txn = self.buy("08012345678", "r4")
        self.assertEqual(txn.status, S.SUCCESS)
        self.assertEqual(txn.provider, "mock")

    def test_adapter_crash_is_not_treated_as_failure(self):
        ProviderRoute.objects.create(service="airtime", provider="crashy", priority=1)
        txn = self.buy("08012345678", "r5")
        self.assertEqual(txn.status, S.PROCESSING)   # no fallback to mock, no refund
        self.assertEqual(self.balance(), 700)

    def test_no_route_refunds(self):
        txn, _ = initiate(self.user, "data", "300", reference="r6", destination="08012345678")
        txn = execute_purchase(txn.pk)
        self.assertEqual(txn.status, S.REFUNDED)
        self.assertEqual(self.balance(), 1000)

class ClaimAndSweeperTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="t2", email="t2@example.com", password="pass12345"
        )
        credit(self.user, "1000", "fund-1")
        ProviderRoute.objects.create(service="airtime", provider="mock", priority=10)

    def new_txn(self, phone, ref):
        txn, _ = initiate(self.user, "airtime", "300", reference=ref, destination=phone)
        return txn

    def make_stale(self, txn):
        # .update() skips auto_now, so we can backdate updated_at
        Transaction.objects.filter(pk=txn.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5)
        )

    def test_claimed_transaction_is_not_sent_again(self):
        txn = self.new_txn("08012345678", "c1")
        Transaction.objects.filter(pk=txn.pk).update(dispatched_at=timezone.now())
        txn = execute_purchase(txn.pk)
        self.assertEqual(txn.status, S.PROCESSING)   # untouched, nothing was sent

    def test_sweeper_redispatches_a_lost_task(self):
        txn = self.new_txn("08012345678", "c2")
        self.make_stale(txn)
        sweep_stuck_transactions()
        txn.refresh_from_db()
        self.assertEqual(txn.status, S.SUCCESS)

    def test_sweeper_requeries_a_timed_out_order(self):
        txn = execute_purchase(self.new_txn("08012349999", "c3").pk)
        self.assertEqual(txn.status, S.PROCESSING)
        self.make_stale(txn)
        sweep_stuck_transactions()
        txn.refresh_from_db()
        self.assertEqual(txn.status, S.SUCCESS)

    def test_sweeper_leaves_fresh_transactions_alone(self):
        txn = self.new_txn("08012345678", "c4")
        sweep_stuck_transactions()
        txn.refresh_from_db()
        self.assertEqual(txn.status, S.PROCESSING)