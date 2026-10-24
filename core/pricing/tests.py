from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from core.common.exceptions import ServiceError

from .models import PriceRuleBase
from .services import resolve_price, rule_for_role

M = PriceRuleBase.Mode
BOTH = (M.FIXED, M.PERCENT_OFF)


def rule(mode, value, role="customer", allowed=BOTH):
    return SimpleNamespace(mode=mode, value=Decimal(value), role=role, allowed_modes=allowed)


class ResolvePriceTests(SimpleTestCase):
    def test_no_rule_means_base_price(self):
        self.assertEqual(resolve_price("1000"), Decimal("1000.00"))

    def test_percent_off(self):
        self.assertEqual(resolve_price("1000", rule(M.PERCENT_OFF, "1.5")), Decimal("985.00"))

    def test_fixed_price(self):
        self.assertEqual(resolve_price("290", rule(M.FIXED, "270")), Decimal("270.00"))

    def test_rounds_half_up(self):
        self.assertEqual(resolve_price("333", rule(M.PERCENT_OFF, "1.5")), Decimal("328.01"))

    def test_disallowed_mode_is_rejected(self):
        bad = rule(M.FIXED, "500", allowed=(M.PERCENT_OFF,))
        with self.assertRaises(ServiceError) as ctx:
            resolve_price("1000", bad)
        self.assertEqual(ctx.exception.code, "PRICING_ERROR")

    def test_zero_price_is_rejected(self):
        with self.assertRaises(ServiceError):
            resolve_price("1000", rule(M.PERCENT_OFF, "100"))

    def test_rule_for_role(self):
        rules = [rule(M.FIXED, "1", role="agent"), rule(M.FIXED, "2", role="reseller")]
        self.assertIs(rule_for_role(rules, "reseller"), rules[1])
        self.assertIsNone(rule_for_role(rules, "customer"))