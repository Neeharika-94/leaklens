import os
from . import services as S
from .models import *
SAMPLE = [
 dict(category="duplicate_subscription", merchant="Zoom", monthly_amount=2000, currency="INR", frequency="monthly", confidence="medium",
      description="Potential overlap between Zoom, Google Meet and Teams.", recommended_action="Review usage and consolidate video-call subscriptions.",
      evidence=["Recurring Zoom charges detected", "Other video conferencing subscriptions detected"],
      calc_inputs=dict(monthly_cost=2000, subscriptions=3, avoidable_monthly_amount=1500)),
 dict(category="unused_subscription", merchant="Figma", monthly_amount=4500, currency="INR", frequency="monthly", confidence="medium",
      description="Design subscription with no usage-related activity for 3 months.", recommended_action="Confirm with the design lead, then cancel or downgrade seats.",
      evidence=["Last related transaction 94 days ago"], calc_inputs=dict(monthly_fee=4500, avoidable_months=9)),
 dict(category="fx_markup", merchant="Foreign currency spend (cards)", monthly_amount=4200, currency="INR", frequency="monthly", confidence="high",
      description="Overseas SaaS and ad spend carries a ~3.5% FX markup.", recommended_action="Move to a low-markup multi-currency card.",
      evidence=["Foreign spend approx 120000/month in INR terms", "3.5% markup on card statement"],
      calc_inputs=dict(monthly_foreign_spend=120000, markup_pct=3.5, alternative_markup_pct=1, months=12)),
 dict(category="idle_card", merchant="Corporate card ending 4821", monthly_amount=500, currency="INR", frequency="monthly", confidence="medium",
      description="Card shows no transactions for 4 months but still incurs a fee.", recommended_action="Close or downgrade the card.",
      evidence=["No transactions Jul-Oct", "Monthly maintenance fee still charged"], calc_inputs=dict(monthly_fee=500, avoidable_monthly_fee=500)),
 dict(category="renewal", merchant="Annual CRM licence", monthly_amount=120000, currency="INR", frequency="annual", confidence="medium",
      description="Annual software renewal approaching.", recommended_action="Negotiate a multi-year discount or right-size seats before renewal.",
      evidence=["Annual charge appeared same month last year"], calc_inputs=dict(renewal_amount=120000, frequency="annual", negotiation_or_cancellation_amount=18000)),
]
DEMO_NOTE = "[DEMO] Simulated submission - not a live Claude connection"
def load_sample(db, user, code):
    return [S.add_finding(db, user, code, {**d, "audit_id": code, "evidence": d["evidence"] + [DEMO_NOTE]})[0].id for d in SAMPLE]
def seed():
    with SessionLocal() as db:
        if db.query(User).filter_by(email="meera@leaklens.demo").first(): return
        m = User(email="meera@leaklens.demo", name="Meera", firm="Meera & Co. Accountants", pw_hash=S.hash_pw("Meera@12345"), currency="INR")
        db.add(m); db.commit()
        c = Customer(accountant_id=m.id, company="Northwind Technologies", slug="northwind", industry="Technology", contact="Arjun", email="arjun@northwind.demo")
        db.add(c); db.commit()
        db.add(Audit(code="LL-NW-2026-001", customer_id=c.id, accountant_id=m.id, title="Q3 spend leak audit (illustrative demo data)", period="Aug-Oct 2026", status="Awaiting Analysis"))
        db.add(ApiToken(user_id=m.id, token_hash=S.sha(os.getenv("DEMO_MCP_TOKEN", "ll_demo_local")), label="demo")); db.commit()
