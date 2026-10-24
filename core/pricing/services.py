import logging
from decimal import ROUND_HALF_UP, Decimal

from core.common.exceptions import ServiceError

from .models import PriceRuleBase

log = logging.getLogger(__name__)
Mode = PriceRuleBase.Mode


def rule_for_role(rules, role):
    """Pick the rule for `role` from rules the caller already fetched."""
    for rule in rules:
        if rule.role == role:
            return rule
    return None


def resolve_price(base_price, rule=None):
    """The price to charge. No rule means the base price."""
    base_price = Decimal(str(base_price))
    if rule is None:
        price = base_price
    else:
        if rule.mode not in rule.allowed_modes:
            log.error("Price rule %r uses a mode it does not allow", rule)
            raise ServiceError("PRICING_ERROR", "This item is temporarily unavailable.")
        value = Decimal(str(rule.value))
        if rule.mode == Mode.FIXED:
            price = value
        else:
            price = base_price * (Decimal("100") - value) / Decimal("100")

    price = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if price <= 0:
        log.error("Resolved a non-positive price from base %s and rule %r", base_price, rule)
        raise ServiceError("PRICING_ERROR", "This item is temporarily unavailable.")
    return price