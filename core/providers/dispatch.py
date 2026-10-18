import logging
from decimal import Decimal

from core.transactions.models import S, Transaction
from core.transactions.services import mark_failed, mark_success, record_attempt

from .base import ProviderResult, ProviderStatus, PurchaseRequest
from .models import ProviderRoute
from .registry import ProviderNotFound, get_adapter

log = logging.getLogger(__name__)


def _request_id(txn):
    return f"txn-{txn.pk}"


def _build_request(txn):
    # Services can put a different value in payload["face_value"] when the
    # amount sent to the vendor differs from what the user paid (e.g. discounts).
    amount = Decimal(str(txn.payload.get("face_value", txn.amount)))
    return PurchaseRequest(
        service=txn.service,
        request_id=_request_id(txn),
        destination=txn.destination,
        amount=amount,
        extra=txn.payload,
    )


def _apply_result(txn, provider, result):
    if result.status == ProviderStatus.SUCCESS:
        return mark_success(txn.pk, provider, result.provider_reference, result.raw)
    if result.status == ProviderStatus.FAILED:
        return mark_failed(txn.pk, result.message or "Provider rejected", provider, result.raw)
    return Transaction.objects.get(pk=txn.pk)  # UNKNOWN: leave as is


def execute_purchase(txn_id):
    """Send a PROCESSING transaction to the providers, in priority order."""
    txn = Transaction.objects.get(pk=txn_id)
    if txn.status != S.PROCESSING:
        return txn

    request = _build_request(txn)
    routes = ProviderRoute.objects.filter(service=txn.service, is_active=True)
    last_message = "No provider available"

    for route in routes:
        try:
            adapter = get_adapter(route.provider)
        except ProviderNotFound:
            log.error("Route points to unknown provider %s", route.provider)
            continue

        try:
            result = adapter.purchase(request)
        except Exception:
            # A crash or timeout does NOT prove the vendor didn't deliver.
            log.exception("Adapter %s raised during purchase", route.provider)
            result = ProviderResult(ProviderStatus.UNKNOWN, message="Adapter error")

        if result.status == ProviderStatus.UNKNOWN:
            # Stop here: no fallback and no refund. Requery will settle it.
            record_attempt(txn.pk, route.provider, result.provider_reference, result.raw)
            return Transaction.objects.get(pk=txn.pk)

        if result.status == ProviderStatus.SUCCESS:
            return _apply_result(txn, route.provider, result)

        last_message = result.message or last_message  # definitive FAILED: try next

    return mark_failed(txn.pk, last_message)


def requery(txn_id):
    """Ask the provider that took the order what happened to it."""
    txn = Transaction.objects.get(pk=txn_id)
    if txn.status != S.PROCESSING or not txn.provider:
        return txn
    try:
        adapter = get_adapter(txn.provider)
        result = adapter.requery(_request_id(txn))
    except Exception:
        log.exception("Requery failed for transaction %s", txn.pk)
        return txn
    return _apply_result(txn, txn.provider, result)