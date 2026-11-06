# LeakLens – AI-Powered Audit & Expense Leakage Detection

LeakLens is an audit and expense leakage detection platform that uses Claude-assisted analysis to identify potential financial irregularities. It stores structured findings, performs deterministic calculations using Python Decimal, enables accountant approval, generates founder-facing reports, and tracks savings.

## Live Demo

**Application:** [Add your Render URL here]

**Demo Login:**
- Email: `meera@leaklens.demo`
- Password: `Meera@12345`

## Run Locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tests/test_calc.py
uvicorn app.main:application --reload
```

Open: `http://localhost:8000`

**Local MCP URL:** `http://localhost:8000/mcp/ll_demo_local`

## Deployment

Deployed using Render (Free Tier), connected to GitHub through a Blueprint using `render.yaml`.

**Note:** The free hosting service may sleep after inactivity, and its local database may reset after restarts or redeployments. Demo data is automatically re-seeded.

## Implemented Features

- Login and seeded demo account
- Audit dashboard and findings management
- Approve, reject, edit, delete and add findings
- Financial calculators
- Audit report publishing
- Founder-facing reports with comments and ownership tracking
- Savings tracking
- Hosted MCP server with 12 tools
- Simulated Claude demo mode

## Planned Features (Phase 2)

- Admin panel
- Payment integration
- Email notifications and workflows
- PDF/CSV exports
- Password-protected reports
- Report revocation interface
- Database migrations