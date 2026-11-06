"""Business logic shared by REST API and MCP server. Every function enforces ownership."""
import hashlib, json, secrets
from datetime import timedelta
from decimal import Decimal
from . import calc
from .models import *

class Forbidden(Exception): ...
class NotFound(Exception): ...
sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.scrypt(p.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
def check_pw(p, h): return secrets.compare_digest(hash_pw(p, h.split("$")[0]), h)

def issue_token(db, user_id, label="claude"):
    raw = "ll_" + secrets.token_urlsafe(32)
    db.add(ApiToken(user_id=user_id, token_hash=sha(raw), label=label)); db.commit(); return raw
def user_from_token(db, raw):
    t = db.query(ApiToken).filter_by(token_hash=sha(raw or ""), revoked=False).first()
    u = t and db.get(User, t.user_id)
    if not u or not u.active or u.role != "accountant": raise Forbidden("invalid or revoked token")
    t.last_used = now(); db.commit(); return u

def get_audit(db, user, code):
    a = db.query(Audit).filter_by(code=code).first()
    if not a or a.accountant_id != user.id: raise NotFound("audit not found")  # same error: no existence leak
    return a
def own_finding(db, user, fid):
    f = db.get(Finding, fid)
    if not f or f.deleted or get_audit_by_id(db, user, f.audit_id) is None: raise NotFound("finding not found")
    return f
def get_audit_by_id(db, user, aid):
    a = db.get(Audit, aid); return a if a and a.accountant_id == user.id else None

def fp(code, d): return sha(json.dumps([code, d["category"], d["merchant"].lower(), str(d.get("monthly_amount")), d.get("frequency")]))
def recalc(f):
    """Run engine; potential stays 0 until an avoidable amount is supplied/confirmed."""
    inputs = dict(f.calc_inputs or {})
    try:
        r = calc.calculate(f.category, inputs) if inputs else None
    except ValueError: r = None
    if r: f.calc_result, f.potential, f.annual_expense = r, Decimal(r["potential"]), Decimal(r["outputs"].get("annual_expense", "0"))
    return f
def snapshot(db, f, by):
    db.add(FindingVersion(finding_id=f.id, by=by, snapshot={c.name: str(getattr(f, c.name)) for c in f.__table__.columns}))

def add_finding(db, user, code, d):
    a = get_audit(db, user, code)
    calc.currency(d.get("currency")); calc.D(d.get("monthly_amount"), "monthly_amount")
    key = fp(code, d)
    ex = db.query(Finding).filter_by(audit_id=a.id, fingerprint=key).first()
    if ex: return ex, True
    f = Finding(audit_id=a.id, fingerprint=key, category=d["category"], merchant=d["merchant"], currency=d["currency"].upper(),
                frequency=d.get("frequency", "monthly"), description=d.get("description"), evidence=d.get("evidence", []),
                confidence=d.get("confidence", "low"), original=d, recommendation=d.get("recommended_action"),
                calc_inputs=d.get("calc_inputs") or {}, annual_expense=calc.annualise(d["monthly_amount"], d.get("frequency", "monthly")))
    recalc(f); db.add(f)
    if a.status in ("Draft", "Awaiting Analysis"): a.status = "Findings Received"
    db.commit(); return f, False

EDITABLE = {"merchant", "description", "approved_recommendation", "priority", "owner", "calc_inputs", "private_notes"}
def update_finding(db, user, fid, changes):
    f = own_finding(db, user, fid); snapshot(db, f, user.email)
    for k, v in changes.items():
        if k not in EDITABLE: raise ValueError(f"field '{k}' is not editable")
        setattr(f, k, v)
    recalc(f)
    if f.review_status == "Approved": f.approved = f.potential   # recalculate approved total after assumption edit
    db.commit(); return f
def review(db, user, fid, status):
    if status not in ("Approved", "Rejected", "Needs Correction", "Pending"): raise ValueError("bad status")
    f = own_finding(db, user, fid); snapshot(db, f, user.email)
    f.review_status = status; f.approved = f.potential if status == "Approved" else Decimal(0)
    if status != "Approved": f.realised = Decimal(0)
    db.commit(); return f
def delete_finding(db, user, fid):
    f = own_finding(db, user, fid); snapshot(db, f, user.email); f.deleted = True; f.realised = f.approved = Decimal(0); db.commit()

def set_action(db, f, status, who):
    if status not in ("Open", "In Progress", "Fixed", "Dismissed"): raise ValueError("bad status")
    f.action_status = status
    # realised only counts for accountant-approved, fixed findings; never rejected/dismissed
    f.realised = f.approved if (status == "Fixed" and f.review_status == "Approved") else Decimal(0)
    db.commit()

def summary(db, user, code):
    return _sum(db, get_audit(db, user, code))
def _sum(db, a):
    fs = db.query(Finding).filter_by(audit_id=a.id, deleted=False).all()
    live = [f for f in fs if f.review_status != "Rejected" and f.action_status != "Dismissed"]
    pot = sum((f.potential for f in live), Decimal(0)); apr = sum((f.approved for f in live), Decimal(0))
    rea = sum((f.realised for f in live), Decimal(0))
    return {"audit_id": a.code, "status": a.status, "findings": len(fs), "potential_annual_savings": str(pot),
            "approved_savings": str(apr), "realised_savings": str(rea),
            "realisation_rate_pct": str(calc.q(rea / apr * 100)) if apr else "0.00",
            "fixed": sum(f.action_status == "Fixed" for f in fs), "dismissed": sum(f.action_status == "Dismissed" for f in fs)}

def fdict(f): return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in
    {"id": f.id, "category": f.category, "merchant": f.merchant, "currency": f.currency, "description": f.description,
     "evidence": f.evidence, "recommendation": f.recommendation, "approved_recommendation": f.approved_recommendation,
     "annual_expense": f.annual_expense, "potential": f.potential, "approved": f.approved, "realised": f.realised,
     "priority": f.priority, "owner": f.owner, "review_status": f.review_status, "action_status": f.action_status}.items()}

def publish(db, user, code, days=30):
    a = get_audit(db, user, code)
    if not db.query(Finding).filter_by(audit_id=a.id, deleted=False, review_status="Approved").count():
        raise ValueError("approve at least one finding before publishing")
    raw = secrets.token_urlsafe(24)
    db.add(Share(audit_id=a.id, token_hash=sha(raw), expires=now() + timedelta(days=days))); a.status = "Published"; db.commit()
    return f"/report/{raw}"
def share_audit(db, token):
    s = db.query(Share).filter_by(token_hash=sha(token), revoked=False).first()
    exp = s and (s.expires.replace(tzinfo=timezone.utc) if s.expires.tzinfo is None else s.expires)
    if not s or exp < now(): raise NotFound("link invalid, revoked or expired")
    return db.get(Audit, s.audit_id)
def public_report(db, token):
    a = share_audit(db, token)  # whitelist only: no original JSON, no private_notes, no fingerprints
    fs = [f for f in db.query(Finding).filter_by(audit_id=a.id, deleted=False, review_status="Approved")]
    acc = db.get(User, a.accountant_id)
    return {"summary": _sum(db, a), "firm": acc.firm, "audit": {"id": a.code, "title": a.title, "period": a.period},
            "findings": [fdict(f) for f in fs],
            "comments": {f.id: [{"author": c.author, "body": c.body} for c in db.query(Comment).filter_by(finding_id=f.id)] for f in fs}}
def log(db, uid, tool, ok, err=None): db.add(ToolLog(user_id=uid, tool=tool, ok=ok, error=err)); db.commit()
