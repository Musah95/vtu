import re
from decimal import ROUND_HALF_UP, Decimal

from core.providers.dispatch import execute_purchase
from core.transactions.models import S
from core.transactions.services import initiate

from .models import AirtimePricing, Network

SERVICE = "airtime"


class AirtimeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_phone(raw):
    """Accepts 08012345678, +2348012345678, 2348012345678 -> 08012345678."""
    digits = re.sub(r"[\s\-]", "", str(raw))
    if digits.startswith("+234"):
        digits = "0" + digits[4:]
    elif digits.startswith("234") and len(digits) == 13:
        digits = "0" + digits[3:]
    if not re.fullmatch(r"0[789][01]\d{8}", digits):
        raise AirtimeError("INVALID_NUMBER", "Enter a valid Nigerian phone number.")
    return digits


def get_network(code):
    try:
        return Network.objects.get(code=code, is_active=True)
    except Network.DoesNotExist:
        raise AirtimeError("INVALID_NETWORK", "Unknown or unavailable network.")


def quote(user, network, amount):
    """What this user pays for `amount` of airtime on this network."""
    if not (network.min_amount <= amount <= network.max_amount):
        raise AirtimeError(
            "INVALID_AMOUNT",
            f"Amount must be between {network.min_amount} and {network.max_amount}.",
        )
    rule = AirtimePricing.objects.filter(network=network, role=user.role).first()
    discount = rule.discount_percent if rule else Decimal("0")
    price = amount * (Decimal("100") - discount) / Decimal("100")
    return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def purchase(user, network, phone, amount, reference=None):
    """
    Returns (transaction, created).
    created=False means this reference was already used: nothing new happened.
    """
    net = get_network(network)
    phone = normalize_phone(phone)
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    price = quote(user, net, amount)

    txn, created = initiate(
        user, SERVICE, price,
        reference=reference,
        destination=phone,
        payload={"network": net.code, "face_value": str(amount)},
    )
    if created and txn.status == S.PROCESSING:
        # Runs inside the web request for now; we'll move this to a Celery task.
        txn = execute_purchase(txn.pk)
    return txn, created