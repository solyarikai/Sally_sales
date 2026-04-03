# Local Development Environment

The backend `.env` file at `backend/.env` is already configured for local development. Just start the backend and it connects directly to the Hetzner production DB (no SSH tunnel needed since the DB port is open).

---

## Quick Start

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001

# Terminal 2: Frontend
cd frontend
npm run dev
```

Backend: http://localhost:8001
Frontend: http://localhost:5173

---

## Required: Database

```bash
# Direct connection to Hetzner production DB (port is open)
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@46.62.210.24:5432/leadgen
```

## Required: Redis

```bash
# Local Redis (run via Docker or brew)
REDIS_URL=redis://localhost:6379/0
```

## Required: OpenAI

```bash
# Used for: search query generation, website analysis/scoring, auto-review, conversation analysis
OPENAI_API_KEY=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
DEFAULT_OPENAI_MODEL=gpt-4o-mini
```

## Required: Outreach Integrations

```bash
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc
SLACK_BOT_TOKEN=xoxb-5059703821363-10410114252597-Vm4M95iovQPBhzdFBuGalj7m
```

## Required: Search Pipeline

```bash
# Yandex Search API — used for domain discovery
YANDEX_SEARCH_API_KEY=AQVNyM68azFp-ua5Gx9UKCi2kjd9ceASfYLYLYhd
YANDEX_SEARCH_FOLDER_ID=b1ghcrnch8s4l0saftba
```

## Optional: Crona API (website scraping via headless browser)

```bash
# Account: pn@getsally.io — 1 credit per website scrape
# API docs: docs/crona.yaml (OpenAPI spec)
# Base URL: https://api.crona.ai
CRONA_EMAIL=pn@getsally.io
CRONA_PASSWORD=Qweqweqwe1
```

## Optional: Google Sheets/Drive

```bash
GOOGLE_APPLICATION_CREDENTIALS=../google-credentials.json
GOOGLE_IMPERSONATE_EMAIL=services@getsally.io
SHARED_DRIVE_ID=0AEvTjlJFlWnZUk9PVA
```

## Optional: Debug Settings

```bash
DEBUG=true
LOG_LEVEL=INFO
```

---

## Complete backend/.env File

```bash
# Database - direct connection to Hetzner production
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@46.62.210.24:5432/leadgen

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=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
DEFAULT_OPENAI_MODEL=gpt-4o-mini

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Google Sheets/Drive
GOOGLE_APPLICATION_CREDENTIALS=../google-credentials.json
GOOGLE_IMPERSONATE_EMAIL=services@getsally.io
SHARED_DRIVE_ID=0AEvTjlJFlWnZUk9PVA

# Outreach integrations
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc
SLACK_BOT_TOKEN=xoxb-5059703821363-10410114252597-Vm4M95iovQPBhzdFBuGalj7m

# Search pipeline
YANDEX_SEARCH_API_KEY=AQVNyM68azFp-ua5Gx9UKCi2kjd9ceASfYLYLYhd
YANDEX_SEARCH_FOLDER_ID=b1ghcrnch8s4l0saftba

# Crona (website scraping, 1 credit per scrape)
CRONA_EMAIL=pn@getsally.io
CRONA_PASSWORD=Qweqweqwe1

# Debug
DEBUG=true
LOG_LEVEL=INFO
```

---

## Running Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/test_api/ -v
```
