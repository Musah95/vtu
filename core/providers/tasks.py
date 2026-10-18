import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from core.transactions.models import S, Transaction

from .dispatch import execute_purchase, requery

log = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=2)


@shared_task
def dispatch_purchase(txn_id):
    """Safe to run twice: the claim in execute_purchase lets only one win."""
    execute_purchase(txn_id)


@shared_task
def requery_transaction(txn_id):
    requery(txn_id)


@shared_task
def sweep_stuck_transactions():
    """Runs every minute. Recovers PROCESSING transactions that went quiet."""
    cutoff = timezone.now() - STALE_AFTER
    stuck = Transaction.objects.filter(status=S.PROCESSING, updated_at__lt=cutoff)

    for txn in stuck:
        if txn.dispatched_at is None:
            # The dispatch task was lost (broker restart, etc.): send it again.
            dispatch_purchase.delay(txn.pk)
        elif txn.provider:
            # A vendor has it (or may have it): ask what happened.
            requery_transaction.delay(txn.pk)
        else:
            # Claimed but no vendor recorded: should be very rare.
            log.warning("Transaction %s needs manual review", txn.pk)