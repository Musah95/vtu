from decimal import Decimal

from core.common.exceptions import ServiceError as AirtimeError  # noqa: F401
from core.common.phone import normalize_phone
from core.pricing.services import resolve_price, rule_for_role
from core.providers.tasks import dispatch_purchase
from core.transactions.models import S
from core.transactions.services import initiate

from .models import Network

SERVICE = "airtime"


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
    rule = rule_for_role(network.pricing.all(), user.role)
    return resolve_price(amount, rule)

def purchase(user, network, phone, amount, reference=None, source=""):
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
        source=source,
        payload={"network": net.code, "face_value": str(amount)},
    )
    if created and txn.status == S.PROCESSING:
        dispatch_purchase.delay(txn.pk)
        txn.refresh_from_db()
    return txn, created