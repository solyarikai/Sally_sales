# Local Development Environment

Copy this to `backend/.env.local` and run with `export $(cat .env.local | xargs)` before starting uvicorn.

## Required: Database (via SSH tunnel)

```bash
# Start tunnel first: ssh -L 5433:localhost:5432 hetzner -N
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@localhost:5433/leadgen
```

## Required: Redis (via SSH tunnel)

```bash
# Start tunnel first: ssh -L 6380:localhost:6379 hetzner -N
REDIS_URL=redis://localhost:6380
```

## Required: API Keys

```bash
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZWFtX2lkIjo4MjgsInVzZXJfaWQiOjEwNTgsInNjb3BlcyI6WyJhZG1pbiJdLCJpYXQiOjE3MzY1MDExNzR9.R_skxWr52Bl8tcNR5hSLey84_BMntjiLLjoH31FxV-M
OPENAI_API_KEY=sk-proj-xxx  # Get from team
```

## Optional: Telegram Notifications

```bash
TELEGRAM_BOT_TOKEN=7819187032:AAEgLFfbKblxXpNq7CZwAQK-SG67cEF9Q8E
TELEGRAM_CHAT_ID=312546298
```

## Optional: Debug Settings

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## Complete .env.local File

```bash
# Database - via SSH tunnel to production
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@localhost:5433/leadgen

# Redis - via SSH tunnel
REDIS_URL=redis://localhost:6380

# API Keys
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZWFtX2lkIjo4MjgsInVzZXJfaWQiOjEwNTgsInNjb3BlcyI6WyJhZG1pbiJdLCJpYXQiOjE3MzY1MDExNzR9.R_skxWr52Bl8tcNR5hSLey84_BMntjiLLjoH31FxV-M
OPENAI_API_KEY=sk-proj-xxx

# Telegram
TELEGRAM_BOT_TOKEN=7819187032:AAEgLFfbKblxXpNq7CZwAQK-SG67cEF9Q8E
TELEGRAM_CHAT_ID=312546298

# Debug
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## Quick Start

```bash
# Terminal 1: SSH tunnels
ssh -L 5433:localhost:5432 -L 6380:localhost:6379 hetzner -N

# Terminal 2: Backend
cd backend
export $(cat .env.local | xargs)
uvicorn app.main:app --reload --port 8001
```

Access at http://localhost:8001
