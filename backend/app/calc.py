"""Deterministic Decimal-only financial engine. No AI, no floats."""
from decimal import Decimal, ROUND_HALF_UP
VERSION = "1.0"
CURRENCIES = {"INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD", "CAD"}
PER_YEAR = {"weekly": 52, "monthly": 12, "quarterly": 4, "annual": 1, "yearly": 1}

def D(v, name="value", allow_neg=False):
    if v is None or isinstance(v, bool): raise ValueError(f"{name} is required")
    try: d = Decimal(str(v))
    except Exception: raise ValueError(f"{name} is not a number")
    if not d.is_finite(): raise ValueError(f"{name} must be finite")
    if d < 0 and not allow_neg: raise ValueError(f"{name} must be >= 0")
    return d

def q(d): return d.quantize(Decimal("0.01"), ROUND_HALF_UP)
def currency(c):
    c = (c or "").upper()
    if c not in CURRENCIES: raise ValueError(f"unsupported currency '{c}'")
    return c
def annualise(amount, frequency):
    if frequency not in PER_YEAR: raise ValueError(f"unknown frequency '{frequency}'")
    return q(D(amount, "amount") * PER_YEAR[frequency])
def convert(amount, rate=1):
    r = D(rate, "fx_rate")
    if r <= 0: raise ValueError("fx_rate must be > 0")
    return q(D(amount, "amount") * r)

def _out(formula, inputs, **o):
    return {"version": VERSION, "formula": formula, "inputs": {k: str(v) for k, v in inputs.items()},
            "outputs": {k: str(q(v)) for k, v in o.items()}, "potential": str(q(o["annual_potential_savings"]))}

def duplicate(i):
    avoid = D(i.get("avoidable_monthly_amount"), "avoidable_monthly_amount")
    return _out("avoidable_monthly x 12", i, annual_potential_savings=avoid * 12,
                annual_expense=D(i.get("monthly_cost", 0), "monthly_cost") * D(i.get("subscriptions", 1), "subscriptions") * 12)

def unused(i):
    fee, mo = D(i.get("monthly_fee"), "monthly_fee"), D(i.get("avoidable_months"), "avoidable_months")
    return _out("monthly_fee x avoidable_months", i, annual_potential_savings=fee * mo, annual_expense=fee * 12)

def fx(i):
    spend, mk = D(i.get("monthly_foreign_spend"), "monthly_foreign_spend"), D(i.get("markup_pct"), "markup_pct")
    months = D(i.get("months", 12), "months")
    alt = D(i.get("alternative_markup_pct", mk), "alternative_markup_pct")
    monthly_cost = spend * mk / 100
    saving_m = spend * max(mk - alt, Decimal(0)) / 100  # only the difference is avoidable
    return _out("spend x markup/100; saving = spend x (markup-alt)/100", i, monthly_fx_cost=monthly_cost,
                annual_fx_estimate=monthly_cost * 12, annual_expense=monthly_cost * 12,
                annual_potential_savings=saving_m * months)

def idle_card(i):
    confirmed = D(i.get("avoidable_monthly_fee", 0), "avoidable_monthly_fee") * 12 \
        + D(i.get("avoidable_annual_fee", 0), "avoidable_annual_fee") + D(i.get("other_avoidable", 0), "other_avoidable")
    total = D(i.get("monthly_fee", 0), "monthly_fee") * 12 + D(i.get("annual_fee", 0), "annual_fee")
    return _out("confirmed avoidable fees only", i, annual_expense=total, annual_potential_savings=confirmed)

def recurring(i):
    a = annualise(i.get("amount"), i.get("frequency"))
    inc = D(i["new_amount"], "new_amount") - D(i.get("amount"), "amount") if "new_amount" in i else Decimal(0)
    return _out("amount x periods per year", i, annual_expense=a, price_change_per_period=inc, annual_potential_savings=Decimal(0))

def renewal(i):
    freq = i.get("frequency", "annual")
    amt = annualise(i.get("renewal_amount"), freq)
    sav = D(i.get("negotiation_or_cancellation_amount", 0), "negotiation_or_cancellation_amount")
    if sav > D(i.get("renewal_amount"), "renewal_amount"): raise ValueError("saving cannot exceed renewal amount")
    return _out("approved saving per renewal x renewals/year", i, annual_expense=amt, annual_potential_savings=sav * PER_YEAR[freq])

def custom(i):
    t, a, b = i.get("template"), D(i.get("a"), "a"), D(i.get("b"), "b")
    r = {"multiply": a * b, "percent_of": a * b / 100, "sum": a + b}.get(t)
    if r is None: raise ValueError("template must be multiply|percent_of|sum")
    return _out(f"template:{t}", i, annual_potential_savings=r)

CALCULATORS = {"duplicate_subscription": duplicate, "unused_subscription": unused, "fx_markup": fx,
               "idle_card": idle_card, "recurring_expense": recurring, "renewal": renewal, "custom": custom}
def calculate(category, inputs):
    if category not in CALCULATORS: raise ValueError(f"unknown category '{category}'")
    return CALCULATORS[category](inputs or {})
