# LeakLens prototype
Claude analyses statements; LeakLens stores structured findings, calculates (Decimal, no AI), gets accountant approval, shares a founder report and tracks savings.

## Run locally
    cd backend
    python -m venv .venv
    .venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    python tests/test_calc.py
    uvicorn app.main:application --reload
Open http://localhost:8000. Login: meera@leaklens.demo / Meera@12345. MCP URL: http://localhost:8000/mcp/ll_demo_local

## Deploy (Render, free)
Push to GitHub -> Render: New > Blueprint > select repo (uses render.yaml). The Connect page shows the live MCP URL.
Free tier sleeps when idle and resets its database on restart; demo data is re-seeded automatically.

## Status
Implemented: login, seeded demo, audit view, approve/reject/edit/delete/add, calculators, publish + founder report (comment, owner, fixed/dismissed), savings tracking, hosted MCP (12 tools), simulate-Claude demo mode (labelled).
Not implemented (phase 2): admin panel, payments, email flows, PDF/CSV export, link password, revoke UI, migrations.
