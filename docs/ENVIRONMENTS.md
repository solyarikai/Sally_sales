# Environments

Three ways to run the system. All share the same codebase, differing only in where services run and which database they connect to.

---

## 1. Local Dev (Native) — recommended for daily work

Run Postgres + Redis in Docker, everything else natively for fast iteration.

```bash
# Start infrastructure
docker compose -f docker-compose.dev.yml up -d

# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001

# Terminal 2: Frontend
cd frontend
npm run dev          # → http://localhost:5179
```

| Service   | URL                     | Notes                          |
|-----------|-------------------------|--------------------------------|
| Frontend  | http://localhost:5179   | Vite dev server, HMR           |
| Backend   | http://localhost:8001   | uvicorn with --reload          |
| Postgres  | localhost:5432          | Local container (leadgen/leadgen123) |
| Redis     | localhost:6379          | Local container               |

**Config:** `backend/.env` — see [docs/ENV_LOCAL.md](ENV_LOCAL.md) for all required keys.

> The default `backend/.env` connects to the **Hetzner production DB** (not the local container). To use the local Postgres, set `DATABASE_URL=postgresql+asyncpg://leadgen:leadgen123@localhost:5432/leadgen`.

---

## 2. Local Dev (Full Docker)

All services in Docker. Useful for testing the production-like setup locally.

```bash
docker compose up --build -d
```

| Service   | URL                     | Notes                          |
|-----------|-------------------------|--------------------------------|
| Frontend  | http://localhost:80     | Nginx serving built assets     |
| Backend   | http://localhost:8000   | Gunicorn inside container      |
| Postgres  | localhost:5432          | Container (leadgen/leadgen_secret) |
| Redis     | localhost:6379          | Container                     |

**Config:** `.env` at repo root (loaded via `env_file` in docker-compose.yml).

---

## 3. Hetzner Production

Server: `46.62.210.24` (SSH alias: `hetzner`)

```bash
# Deploy latest code
ssh hetzner 'bash ~/magnum-opus-project/repo/scripts/deploy.sh'
```

The deploy script:
1. Stops the pipeline if running
2. `git pull origin datamodel`
3. `docker-compose up --build -d`
4. Waits for backend health check
5. Restarts the pipeline if it was running

| Service   | URL                     | Notes                          |
|-----------|-------------------------|--------------------------------|
| Frontend  | http://46.62.210.24     | Port 80, Nginx                 |
| Backend   | http://46.62.210.24:8000| Internal, proxied by Nginx     |
| Postgres  | 46.62.210.24:5432       | Port open (used by local dev)  |
| Redis     | localhost:6379          | Container, not exposed         |

**Config:** `~/magnum-opus-project/repo/.env` on the server.

---

## API Keys & Secrets

All API keys are documented in [docs/ENV_LOCAL.md](ENV_LOCAL.md). Do not duplicate them here.
