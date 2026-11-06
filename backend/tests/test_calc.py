import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from decimal import Decimal
from app import calc
class T(unittest.TestCase):
    def test_duplicate(self): self.assertEqual(calc.calculate("duplicate_subscription", {"avoidable_monthly_amount": "2000"})["potential"], "24000.00")
    def test_no_float_drift(self): self.assertEqual(calc.calculate("unused_subscription", {"monthly_fee": 0.1, "avoidable_months": 3})["potential"], "0.30")
    def test_fx_only_difference_saved(self):
        r = calc.calculate("fx_markup", {"monthly_foreign_spend": 100000, "markup_pct": 3.5, "alternative_markup_pct": 1, "months": 12})
        self.assertEqual(r["outputs"]["annual_fx_estimate"], "42000.00"); self.assertEqual(r["potential"], "30000.00")
    def test_idle_card_confirmed_only(self): self.assertEqual(calc.calculate("idle_card", {"monthly_fee": 100, "avoidable_annual_fee": 500})["potential"], "500.00")
    def test_quarterly(self): self.assertEqual(calc.annualise(1000, "quarterly"), Decimal("4000.00"))
    def test_renewal(self): self.assertEqual(calc.calculate("renewal", {"renewal_amount": 120000, "frequency": "annual", "negotiation_or_cancellation_amount": 18000})["potential"], "18000.00")
    def test_zero(self): self.assertEqual(calc.calculate("unused_subscription", {"monthly_fee": 0, "avoidable_months": 0})["potential"], "0.00")
    def test_negative(self):
        with self.assertRaises(ValueError): calc.calculate("unused_subscription", {"monthly_fee": -1, "avoidable_months": 1})
    def test_missing(self):
        with self.assertRaises(ValueError): calc.calculate("duplicate_subscription", {})
    def test_bad_currency(self):
        with self.assertRaises(ValueError): calc.currency("XXX")
    def test_bad_category(self):
        with self.assertRaises(ValueError): calc.calculate("nope", {})
    def test_custom(self): self.assertEqual(calc.calculate("custom", {"template": "percent_of", "a": 1000, "b": 5})["potential"], "50.00")
if __name__ == "__main__": unittest.main()
