from core.common.exceptions import ServiceError
from core.common.phone import normalize_phone
from core.providers.tasks import dispatch_purchase
from core.transactions.models import S
from core.transactions.services import initiate
from core.pricing.services import resolve_price, rule_for_role
from .models import DataPlan

SERVICE = "data"


def get_plan(plan_id):
    try:
        return DataPlan.objects.get(pk=plan_id, is_active=True)
    except DataPlan.DoesNotExist:
        raise ServiceError("INVALID_PLAN", "Unknown or unavailable data plan.")


def price_for(user, plan):
    """The role-specific price if a rule exists, otherwise the base price."""
    rule = rule_for_role(plan.prices.all(), user.role)
    return resolve_price(plan.base_price, rule)


def purchase(user, plan_id, phone, reference=None):
    """
    Returns (transaction, created).
    created=False means this reference was already used: nothing new happened.
    """
    plan = get_plan(plan_id)
    phone = normalize_phone(phone)
    price = price_for(user, plan)

    txn, created = initiate(
        user, SERVICE, price,
        reference=reference,
        destination=phone,
        # Snapshot the plan details: later edits to the plan must not rewrite history.
        payload={
            "network": plan.network,
            "plan_id": plan.pk,
            "plan_name": plan.name,
            "plan_code": plan.provider_code,
            "validity": plan.validity,
        },
    )
    if created and txn.status == S.PROCESSING:
        dispatch_purchase.delay(txn.pk)
        txn.refresh_from_db()
    return txn, created