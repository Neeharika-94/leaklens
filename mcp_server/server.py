"""LeakLens MCP server (stdio). Auth: LEAKLENS_MCP_TOKEN issued in the app via POST /mcp-tokens.
Claude analyses statements itself and submits STRUCTURED findings; this server never sees raw statements."""
import os, sys
from contextvars import ContextVar
TOKEN = ContextVar("leaklens_token", default=None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from mcp.server.fastmcp import FastMCP
from app import services as S, calc
from app.models import *
init(); mcp = FastMCP("leaklens", host="0.0.0.0", stateless_http=True, json_response=True)

def run(tool, fn):
    with SessionLocal() as db:
        try:
            u = S.user_from_token(db, TOKEN.get() or os.getenv("LEAKLENS_MCP_TOKEN"))
            out = fn(db, u); S.log(db, u.id, tool, True); return out
        except Exception as e:
            S.log(db, None, tool, False, type(e).__name__); return {"error": str(e)}

@mcp.tool()
def get_customers() -> dict:
    """List the authenticated accountant's customers."""
    return run("get_customers", lambda db, u: [{"id": c.id, "company": c.company, "slug": c.slug}
               for c in db.query(Customer).filter_by(accountant_id=u.id, archived=False)])
@mcp.tool()
def create_audit(code: str, customer_id: int, title: str, period: str) -> dict:
    """Create an audit for an existing customer."""
    def f(db, u):
        c = db.get(Customer, customer_id)
        if not c or c.accountant_id != u.id: raise S.NotFound("customer not found")
        db.add(Audit(code=code, customer_id=customer_id, accountant_id=u.id, title=title, period=period, status="Awaiting Analysis")); db.commit(); return {"audit_id": code}
    return run("create_audit", f)
@mcp.tool()
def add_finding(finding: dict) -> dict:
    """Add one structured finding. Required: audit_id, category, merchant, monthly_amount, currency. Duplicates are ignored."""
    def f(db, u):
        x, dup = S.add_finding(db, u, finding["audit_id"], finding); return {"finding_id": x.id, "duplicate": dup, "potential": str(x.potential)}
    return run("add_finding", f)
@mcp.tool()
def add_findings_bulk(audit_id: str, findings: list[dict]) -> dict:
    """Add many findings atomically-per-item; returns IDs and per-item errors."""
    def f(db, u):
        res = []
        for d in findings:
            try: x, dup = S.add_finding(db, u, audit_id, {**d, "audit_id": audit_id}); res.append({"finding_id": x.id, "duplicate": dup})
            except Exception as e: db.rollback(); res.append({"error": str(e)})
        return {"results": res, "summary": S.summary(db, u, audit_id)}
    return run("add_findings_bulk", f)
@mcp.tool()
def update_finding(finding_id: int, changes: dict) -> dict:
    """Update editable fields (merchant, description, priority, owner, calc_inputs...). Original submission is preserved."""
    return run("update_finding", lambda db, u: S.fdict(S.update_finding(db, u, finding_id, changes)))
@mcp.tool()
def delete_finding(finding_id: int) -> dict:
    """Soft-delete a finding (history retained)."""
    return run("delete_finding", lambda db, u: (S.delete_finding(db, u, finding_id), {"ok": True})[1])
@mcp.tool()
def calculate_savings(category: str, inputs: dict) -> dict:
    """Run the deterministic calculator (no AI). Categories: duplicate_subscription, unused_subscription, fx_markup, idle_card, recurring_expense, renewal, custom."""
    return run("calculate_savings", lambda db, u: calc.calculate(category, inputs))
@mcp.tool()
def list_findings(audit_id: str) -> dict:
    """List findings for an audit."""
    def f(db, u):
        a = S.get_audit(db, u, audit_id); return [S.fdict(x) for x in db.query(Finding).filter_by(audit_id=a.id, deleted=False)]
    return run("list_findings", f)
@mcp.tool()
def get_audit(audit_id: str) -> dict:
    """Audit state with findings."""
    def f(db, u):
        a = S.get_audit(db, u, audit_id)
        return {"summary": S.summary(db, u, audit_id), "findings": [S.fdict(x) for x in db.query(Finding).filter_by(audit_id=a.id, deleted=False)]}
    return run("get_audit", f)
@mcp.tool()
def get_audit_summary(audit_id: str) -> dict:
    """Totals: potential, approved, realised, realisation rate."""
    return run("get_audit_summary", lambda db, u: S.summary(db, u, audit_id))
@mcp.tool()
def get_audit_status(audit_id: str) -> dict:
    """Founder actions, comments and savings progress."""
    def f(db, u):
        a = S.get_audit(db, u, audit_id); fs = db.query(Finding).filter_by(audit_id=a.id, deleted=False).all()
        return {"summary": S.summary(db, u, audit_id), "actions": [{"id": x.id, "merchant": x.merchant, "action_status": x.action_status, "owner": x.owner,
                "comments": [c.body for c in db.query(Comment).filter_by(finding_id=x.id)]} for x in fs]}
    return run("get_audit_status", f)
@mcp.tool()
def publish_report(audit_id: str, expires_in_days: int = 30) -> dict:
    """Publish an audit (needs >=1 accountant-approved finding) and return a secure link path."""
    return run("publish_report", lambda db, u: {"report_url": S.publish(db, u, audit_id, expires_in_days)})
if __name__ == "__main__": mcp.run()
