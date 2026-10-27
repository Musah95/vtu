import re
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.common.exceptions import ServiceError
from core.common.phone import normalize_phone
from core.pricing.services import resolve_price, rule_for_role
from core.providers.base import LookupStatus
from core.providers.dispatch import lookup
from core.providers.tasks import dispatch_purchase
from core.transactions.models import S, Transaction
from core.transactions.services import initiate

from .models import CablePackage, Operator, SmartcardVerification

SERVICE = "cable"
VERIFICATION_TTL = timedelta(minutes=10)


def normalize_smartcard(raw):
    digits = re.sub(r"[\s\-]", "", str(raw))
    if not re.fullmatch(r"\d{10,11}", digits):
        raise ServiceError(
            "INVALID_SMARTCARD", "Enter a valid smartcard / IUC number (10 or 11 digits)."
        )
    return digits


def verify(user, operator, smartcard):
    """Ask the vendor who owns this card. Moves no money and creates no transaction."""
    if operator not in Operator.values:
        raise ServiceError("INVALID_OPERATOR", "Unknown cable operator.")
    smartcard = normalize_smartcard(smartcard)

    result = lookup(SERVICE, smartcard, extra={"operator": operator})
    if result.status == LookupStatus.INVALID:
        raise ServiceError(
            "INVALID_SMARTCARD",
            "We couldn't find that smartcard. Check the number and the operator.",
        )
    if result.status != LookupStatus.VALID:
        raise ServiceError(
            "VERIFICATION_UNAVAILABLE",
            "We couldn't verify this smartcard right now. Please try again shortly.",
        )
    return SmartcardVerification.objects.create(
        user=user, operator=operator, smartcard=smartcard,
        customer_name=result.customer_name, details=result.details,
        expires_at=timezone.now() + VERIFICATION_TTL,
    )


def get_verification(user, verification_id):
    try:
        verification = SmartcardVerification.objects.get(pk=verification_id, user=user)
    except (SmartcardVerification.DoesNotExist, ValidationError, ValueError):
        raise ServiceError("INVALID_VERIFICATION", "Verify the smartcard first.")
    if verification.expires_at <= timezone.now():
        raise ServiceError(
            "VERIFICATION_EXPIRED", "That verification expired. Please verify the smartcard again."
        )
    return verification


def get_package(package_id):
    try:
        return CablePackage.objects.get(pk=package_id, is_active=True)
    except CablePackage.DoesNotExist:
        raise ServiceError("INVALID_PACKAGE", "Unknown or unavailable package.")


def price_for(user, package):
    rule = rule_for_role(package.prices.all(), user.role)
    return resolve_price(package.base_price, rule)

def purchase(user, verification_id, package_id, phone="", reference=None, source=""):
    """
    Returns (transaction, created).
    created=False means this reference was already used: nothing new happened.
    """
    # A retry must get the original order back, even if its verification has
    # expired in the meantime, so check the reference before anything else.
    if reference:
        existing = Transaction.objects.filter(user=user, reference=reference).first()
        if existing:
            return existing, False

    verification = get_verification(user, verification_id)
    package = get_package(package_id)
    if package.operator != verification.operator:
        raise ServiceError(
            "PACKAGE_MISMATCH", "That package isn't available for this smartcard's operator."
        )
    price = price_for(user, package)
    phone = normalize_phone(phone) if phone else ""

    txn, created = initiate(
        user, SERVICE, price,
        reference=reference,
        destination=verification.smartcard,       # from the stored verification, never the client
        source=source,
        payload={
            "operator": verification.operator,
            "package_id": package.pk,
            "package_name": package.name,
            "package_code": package.provider_code,
            "validity": package.validity,
            "customer_name": verification.customer_name,   # what the customer confirmed
            "verification_id": str(verification.pk),
            "phone": phone,
        },
    )
    if created and txn.status == S.PROCESSING:
        dispatch_purchase.delay(txn.pk)
        txn.refresh_from_db()
    return txn, created