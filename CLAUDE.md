# Magnum Opus — Lead Generation Platform

## Quick Reference
- **Stack**: FastAPI + SQLAlchemy (async) + React 19 + TypeScript + Tailwind + AG Grid
- **Server**: `46.62.210.24` (SSH alias `hetzner`, user `root`)
- **Deploy**: `ssh hetzner 'bash ~/magnum-opus-project/repo/scripts/deploy.sh'`
- **Containers**: leadgen-frontend(:80), leadgen-backend(:8000), leadgen-postgres(:5432), leadgen-redis(:6379), n8n(:5678)
- **DB**: `postgresql+asyncpg://leadgen:...@localhost:5432/leadgen`
- **Google credentials**: `/app/google-credentials.json` (inside backend container)
- **Git identity**: `Danila <danila@magnum-opus.dev>`
- **Branches**: main, datamodel (prod), TAM, Danila (current working branch)

## Key Projects in DB
- **INXY** (id=10): Cross-border B2B crypto payment platform — see `docs/inxy/` for full details
- **EasyStaff RU** (id=40): Global freelancer payment platform (Russian market)
- **EasyStaff Global** (id=9)

## Architecture
- Backend API: `/app/` inside container, FastAPI with async SQLAlchemy
- Frontend: React SPA with AG Grid for data tables
- Services: Apollo, FindyMail, SmartLead, Yandex Search, Google Gemini, GetSales, Clay, Apify
- TAM/Lookalike system: Gemini 2.5 Flash clusters leads by business model, searches for lookalikes via Apollo/Yandex/Google
- Google Sheets integration: `google_sheets_service` for reading/writing project data

## Running Scripts on Server
```bash
# Copy script and execute inside backend container
scp script.py hetzner:/tmp/
ssh hetzner "docker cp /tmp/script.py leadgen-backend:/tmp/ && docker exec leadgen-backend python /tmp/script.py"
```

Scripts that use Google Sheets must import via app service:
```python
import os, sys
sys.path.insert(0, "/app")
os.chdir("/app")
from app.services.google_sheets_service import google_sheets_service
google_sheets_service._initialize()
svc = google_sheets_service.sheets_service
```

## INXY Project — Critical Rules
See `docs/inxy/README.md` for complete business model and product details. Key rules:

1. **INXY is B2B ONLY** — serves merchants/companies, NOT end consumers
2. **NO card processing** — never mention Visa, Mastercard, credit/debit cards
3. **NO B2C on-ramp** — INXY is NOT MoonPay. No widget for users buying crypto
4. **PayOut = crypto only** — recipients get USDT/BTC on wallets, convert to fiat THEMSELVES
5. **OTC = corporate treasury** — for the BUSINESS itself ($50K+), not for users/investors
6. **NO high-risk operators** — no iGaming/gambling/casinos directly, but B2B ecosystem (affiliates, software) is OK
7. **Infrastructure API** — white-label PayGate for PSPs, NOT "on/off-ramp"
