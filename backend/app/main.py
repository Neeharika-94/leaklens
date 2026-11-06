import os, sys, jwt
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from datetime import timedelta
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from . import calc, services as S
from .models import *
SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
init()
from .seed import seed, load_sample
seed()
import mcp_server.server as mcpmod
mcp_app = mcpmod.mcp.streamable_http_app()
@asynccontextmanager
async def lifespan(_):
    async with mcpmod.mcp.session_manager.run(): yield
app = FastAPI(title="LeakLens", lifespan=lifespan)
def db_():
    with SessionLocal() as db: yield db
def me(authorization: str = Header(""), db=Depends(db_)):
    try: uid = jwt.decode(authorization.removeprefix("Bearer "), SECRET, algorithms=["HS256"])["sub"]
    except Exception: raise HTTPException(401, "not authenticated")
    u = db.get(User, int(uid))
    if not u or not u.active: raise HTTPException(401, "inactive")
    return u
def accountant(u=Depends(me)):
    if u.role != "accountant": raise HTTPException(403, "accountants only")
    return u
def guard(fn, *a):
    try: return fn(*a)
    except S.NotFound as e: raise HTTPException(404, str(e))
    except (ValueError, KeyError) as e: raise HTTPException(422, str(e))

class Reg(BaseModel): name: str; firm: str; email: str; password: str = Field(min_length=8); currency: str = "INR"
class Login(BaseModel): email: str; password: str
@app.post("/auth/register")
def register(r: Reg, db=Depends(db_)):
    if db.query(User).filter_by(email=r.email.lower()).first(): raise HTTPException(409, "email in use")
    u = User(email=r.email.lower(), name=r.name, firm=r.firm, pw_hash=S.hash_pw(r.password), currency=calc.currency(r.currency)); db.add(u); db.commit(); return {"id": u.id}
@app.post("/auth/login")
def login(l: Login, db=Depends(db_)):
    u = db.query(User).filter_by(email=l.email.lower()).first()
    if not u or not u.active or not S.check_pw(l.password, u.pw_hash): raise HTTPException(401, "bad credentials")
    return {"token": jwt.encode({"sub": str(u.id), "role": u.role, "exp": now() + timedelta(hours=8)}, SECRET), "role": u.role}

class Cust(BaseModel): company: str; slug: str; industry: str = ""; contact: str = ""; email: str = ""; currency: str = "INR"
@app.post("/customers")
def new_customer(c: Cust, u=Depends(accountant), db=Depends(db_)):
    x = Customer(accountant_id=u.id, **{**c.model_dump(), "currency": calc.currency(c.currency)}); db.add(x); db.commit(); return {"id": x.id}
@app.get("/customers")
def customers(u=Depends(accountant), db=Depends(db_)):
    return [{"id": c.id, "company": c.company, "slug": c.slug} for c in db.query(Customer).filter_by(accountant_id=u.id, archived=False)]
class AuditIn(BaseModel): code: str; customer_id: int; title: str; period: str
@app.post("/audits")
def new_audit(a: AuditIn, u=Depends(accountant), db=Depends(db_)):
    c = db.get(Customer, a.customer_id)
    if not c or c.accountant_id != u.id: raise HTTPException(404, "customer not found")
    x = Audit(accountant_id=u.id, status="Awaiting Analysis", **a.model_dump()); db.add(x); db.commit(); return {"id": x.id}
@app.get("/audits/{code}")
def audit(code: str, u=Depends(accountant), db=Depends(db_)):
    a = guard(S.get_audit, db, u, code)
    return {"summary": S.summary(db, u, code), "findings": [S.fdict(f) for f in db.query(Finding).filter_by(audit_id=a.id, deleted=False)]}
@app.patch("/findings/{fid}")
def edit(fid: int, body: dict, u=Depends(accountant), db=Depends(db_)): return S.fdict(guard(S.update_finding, db, u, fid, body))
@app.post("/findings/{fid}/review/{status}")
def rev(fid: int, status: str, u=Depends(accountant), db=Depends(db_)): return S.fdict(guard(S.review, db, u, fid, status))
@app.delete("/findings/{fid}")
def rm(fid: int, u=Depends(accountant), db=Depends(db_)): guard(S.delete_finding, db, u, fid); return {"ok": True}
@app.post("/audits/{code}/publish")
def pub(code: str, u=Depends(accountant), db=Depends(db_)): return {"url": guard(S.publish, db, u, code)}
@app.get("/public/report/{token}")
def report(token: str, db=Depends(db_)): return guard(S.public_report, db, token)
class Act(BaseModel): status: str | None = None; owner: str | None = None; comment: str | None = None; author: str = "Founder"
@app.post("/public/report/{token}/findings/{fid}")
def founder_act(token: str, fid: int, a: Act, db=Depends(db_)):
    audit = guard(S.share_audit, db, token); f = db.get(Finding, fid)
    if not f or f.audit_id != audit.id or f.deleted or f.review_status != "Approved": raise HTTPException(404, "not found")
    if a.owner: f.owner = a.owner
    if a.comment: db.add(Comment(finding_id=f.id, author=a.author, body=a.comment))
    if a.status: guard(S.set_action, db, f, a.status, a.author)
    db.commit(); return S.fdict(f)   # founder can only touch owner/comment/action status
@app.post("/mcp-tokens")
def mint(u=Depends(accountant), db=Depends(db_)): return {"token": S.issue_token(db, u.id), "note": "shown once"}

from fastapi import Request
@app.get("/audits")
def audits(u=Depends(accountant), db=Depends(db_)):
    return [{"code": a.code, "title": a.title, "period": a.period, "status": a.status, "customer": db.get(Customer, a.customer_id).company}
            for a in db.query(Audit).filter_by(accountant_id=u.id)]
@app.post("/audits/{code}/findings")
def addf(code: str, body: dict, u=Depends(accountant), db=Depends(db_)):
    x, dup = guard(S.add_finding, db, u, code, {**body, "audit_id": code}); return {"finding_id": x.id, "duplicate": dup}
@app.post("/calc")
def calc_(body: dict, u=Depends(accountant)): return guard(calc.calculate, body.get("category"), body.get("inputs"))
@app.post("/demo/simulate/{code}")
def simulate(code: str, u=Depends(accountant), db=Depends(db_)):
    guard(S.get_audit, db, u, code); load_sample(db, u, code); return S.summary(db, u, code)
@app.get("/demo/info")
def info(request: Request, u=Depends(accountant)):
    return {"mcp_url": f"{str(request.base_url).rstrip('/')}/mcp/{os.getenv('DEMO_MCP_TOKEN', 'll_demo_local')}"}
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "..", "frontend"), html=True))

class _Wrap:
    """Routes /mcp/<token> to the MCP app (token stays out of tool args); everything else to the website/API."""
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp/"):
            mcpmod.TOKEN.set(scope["path"].split("/")[2])
            return await mcp_app(dict(scope, path="/mcp", raw_path=b"/mcp"), receive, send)
        return await app(scope, receive, send)
application = _Wrap()
