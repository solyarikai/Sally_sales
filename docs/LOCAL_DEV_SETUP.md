# Local Development Setup

Connect your local backend to the production database on Hetzner.

## Prerequisites

- SSH access to Hetzner server (configured as `hetzner` in ~/.ssh/config)
- Python 3.11+
- The backend code from the repo

## Step 1: Start SSH Tunnel to Remote Database

Open a terminal and run:

```bash
ssh -L 5433:localhost:5432 hetzner -N
```

This forwards local port 5433 to the remote PostgreSQL on port 5432.
Keep this terminal open while developing.

## Step 2: Create Local Environment File

Create `.env.local` in the backend directory:

```bash
# Database - via SSH tunnel to production
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@localhost:5433/leadgen

# Redis - via SSH tunnel (optional, for caching)
# Run: ssh -L 6380:localhost:6379 hetzner -N
REDIS_URL=redis://localhost:6380

# API Keys (same as production)
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZWFtX2lkIjo4MjgsInVzZXJfaWQiOjEwNTgsInNjb3BlcyI6WyJhZG1pbiJdLCJpYXQiOjE3MzY1MDExNzR9.R_skxWr52Bl8tcNR5hSLey84_BMntjiLLjoH31FxV-M
OPENAI_API_KEY=sk-proj-...

# Telegram (for notifications)
TELEGRAM_BOT_TOKEN=7819187032:AAEgLFfbKblxXpNq7CZwAQK-SG67cEF9Q8E
TELEGRAM_CHAT_ID=312546298

# Local settings
DEBUG=true
LOG_LEVEL=DEBUG
```

## Step 3: Run Backend Locally

```bash
cd backend
source .venv/bin/activate  # or create venv if needed
pip install -r requirements.txt

# Load local env
export $(cat .env.local | xargs)

# Run with hot reload
uvicorn app.main:app --reload --port 8001
```

Access at: http://localhost:8001

## Quick Start Script

Save as `start_local.sh`:

```bash
#!/bin/bash

# Start SSH tunnels in background
ssh -L 5433:localhost:5432 -L 6380:localhost:6379 hetzner -N &
SSH_PID=$!
echo "SSH tunnel started (PID: $SSH_PID)"

# Wait for tunnel
sleep 2

# Load env and start backend
cd backend
export $(cat .env.local | xargs)
uvicorn app.main:app --reload --port 8001

# Cleanup on exit
kill $SSH_PID 2>/dev/null
```

## Verify Connection

```bash
# Test database connection
psql postgresql://leadgen:leadgen_secret@localhost:5433/leadgen -c "SELECT COUNT(*) FROM contacts"

# Test API
curl http://localhost:8001/api/health
```

## Notes

- Local backend uses port 8001 to avoid conflicts with remote (8000)
- SSH tunnel required - database is not exposed publicly
- Be careful with writes - you're connected to production data!
