import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.wallet.services import WalletError, credit, debit

from .models import ALLOWED_TRANSITIONS, S, Transaction


class InvalidTransition(Exception):
    pass


def _wallet_ref(txn):
    # Debit and refund share this reference; the ledger's unique constraint
    # (wallet, reference, type) makes each of them happen at most once.
    return f"txn:{txn.pk}"


def _move(txn, new_status):
    if new_status not in ALLOWED_TRANSITIONS[txn.status]:
        raise InvalidTransition(f"{txn.status} -> {new_status} is not allowed")
    txn.status = new_status
    if new_status in (S.SUCCESS, S.FAILED, S.REFUNDED) and txn.completed_at is None:
        txn.completed_at = timezone.now()


def initiate(user, service, amount, reference=None, destination="",
             payload=None, cost_price=None):
    """
    Create a transaction and debit the wallet.
    Returns (txn, created). If created is False, this reference was already
    used: return the existing result and do NOT call the provider again.
    If txn.status is FAILED, the wallet was not debited.
    """
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    reference = reference or uuid.uuid4().hex

    try:
        with transaction.atomic():
            txn = Transaction.objects.create(
                user=user, service=service, reference=reference, amount=amount,
                destination=destination, payload=payload or {}, cost_price=cost_price,
            )
    except IntegrityError:
        return Transaction.objects.get(user=user, reference=reference), False

    try:
        with transaction.atomic():
            txn = Transaction.objects.select_for_update().get(pk=txn.pk)
            debit(user, amount, _wallet_ref(txn), f"{service} purchase")
            _move(txn, S.PROCESSING)
            txn.save()
    except WalletError as exc:
        with transaction.atomic():
            txn = Transaction.objects.select_for_update().get(pk=txn.pk)
            txn.failure_reason = str(exc)
            _move(txn, S.FAILED)
            txn.save()
    return txn, True


@transaction.atomic
def mark_success(txn_id, provider="", provider_reference="", response=None):
    txn = Transaction.objects.select_for_update().get(pk=txn_id)
    if txn.status == S.SUCCESS:
        return txn
    _move(txn, S.SUCCESS)
    txn.provider = provider or txn.provider
    txn.provider_reference = provider_reference
    if response is not None:
        txn.provider_response = response
    txn.save()
    return txn


@transaction.atomic
def mark_failed(txn_id, reason, provider="", response=None):
    """Only call this when the provider DEFINITELY did not deliver."""
    txn = Transaction.objects.select_for_update().get(pk=txn_id)
    if txn.status in (S.FAILED, S.REFUNDED):
        return txn
    if txn.status != S.PROCESSING:
        raise InvalidTransition(f"cannot fail a {txn.status} transaction")
    txn.failure_reason = reason[:255]
    txn.provider = provider or txn.provider
    if response is not None:
        txn.provider_response = response
    _move(txn, S.FAILED)
    credit(txn.user, txn.amount, _wallet_ref(txn), "Refund")
    _move(txn, S.REFUNDED)
    txn.save()
    return txn

@transaction.atomic
def record_attempt(txn_id, provider, provider_reference="", response=None):
    txn = Transaction.objects.select_for_update().get(pk=txn_id)
    txn.provider = provider
    if provider_reference:
        txn.provider_reference = provider_reference
    if response is not None:
        txn.provider_response = response
    txn.save()
    return txn