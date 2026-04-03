# Fast Local Development Guide

This guide shows you how to develop **fast** locally without Docker overhead.

## Why Not Docker for Development?

Docker is great for production, but for local development:
- ❌ Slow rebuilds when you change code
- ❌ File system overhead (especially on macOS)
- ❌ Slower hot reload
- ❌ More complex debugging

## Fast Development Setup

We use a **hybrid approach**:
- ✅ **Docker**: Only for Postgres + Redis (services you don't modify)
- ✅ **Native**: Frontend + Backend (instant hot reload)

## Quick Start

### Option 1: Run Everything (Recommended for first time)

```bash
chmod +x dev.sh
./dev.sh
```

This will:
1. Start Postgres + Redis in Docker
2. Create Python venv if needed
3. Install dependencies if needed
4. Run migrations
5. Start backend with hot reload
6. Start frontend with hot reload

**URLs:**
- Frontend: http://localhost:5173 (Vite dev server)
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Run Backend Only

```bash
chmod +x dev-backend.sh
./dev-backend.sh
```

Use this when you're only working on backend code.

### Option 3: Run Frontend Only

```bash
chmod +x dev-frontend.sh
./dev-frontend.sh
```

Use this when backend is already running and you only need frontend.

## Development Workflow

### Backend Changes
1. Edit any Python file in `backend/`
2. FastAPI auto-reloads instantly (< 1 second)
3. Check terminal for any errors

### Frontend Changes
1. Edit any TypeScript/React file in `frontend/src/`
2. Vite hot-reloads instantly (< 100ms)
3. Browser updates automatically

### Database Changes
1. Edit models in `backend/app/models/`
2. Create migration:
   ```bash
   cd backend
   source venv/bin/activate
   alembic revision --autogenerate -m "Description"
   alembic upgrade head
   ```

## Speed Comparison

| Task | Docker | Native | Speedup |
|------|--------|--------|---------|
| Frontend hot reload | 2-5s | 0.1s | **20-50x faster** |
| Backend reload | 3-8s | 0.5s | **6-16x faster** |
| First start | 60s+ | 10s | **6x faster** |
| Rebuild after changes | 120s+ | 0s | **∞ faster** |

## Manual Setup (if scripts don't work)

### 1. Start Database Services

```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Setup Backend

```bash
cd backend

# Create venv (first time only)
python3 -m venv venv
source venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Copy and configure .env (first time only)
cp .env.dev .env
# Edit .env and add your API keys

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Setup Frontend (in new terminal)

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173 (frontend)
lsof -ti:5173 | xargs kill -9
```

### Database Connection Error

```bash
# Restart database services
docker-compose -f docker-compose.dev.yml restart

# Check if running
docker ps
```

### Python venv Issues

```bash
# Remove and recreate
rm -rf backend/venv
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend Build Issues

```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Production Deployment

When you're ready to deploy, use the original docker-compose:

```bash
docker-compose up -d --build
```

This builds optimized production images.

## Tips for Maximum Speed

1. **Use separate terminals**: One for backend, one for frontend
2. **Keep services running**: Don't restart unless needed
3. **Use an IDE with good TypeScript support**: VSCode recommended
4. **Enable auto-save**: Changes trigger hot reload immediately
5. **Use Python debugger**: Add breakpoints in your IDE instead of print statements

## Environment Variables

Backend `.env` file (copy from `.env.dev`):

```env
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@localhost:5432/leadgen
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=your-key-here
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Debugging

### Backend (Python)
- Use VSCode debugger with FastAPI
- Or add `import pdb; pdb.set_trace()` for breakpoints

### Frontend (TypeScript)
- Use browser DevTools
- React DevTools extension recommended
- Check Vite terminal for build errors

## Database Management

### View data
```bash
# Connect to Postgres
docker exec -it leadgen-postgres-dev psql -U leadgen -d leadgen

# Or use a GUI tool like pgAdmin, DBeaver, or TablePlus
# Connection: localhost:5432, user: leadgen, password: leadgen_secret
```

### Reset database
```bash
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
cd backend && source venv/bin/activate && alembic upgrade head
```

## Redis Debugging

```bash
# Start Redis Commander
docker-compose -f docker-compose.dev.yml --profile debug up -d

# Access at http://localhost:8081
```

## Summary

**For fastest development:**
- Use `./dev.sh` for full setup
- Use `./dev-backend.sh` when only working on backend
- Use `./dev-frontend.sh` when only working on frontend
- Docker only for Postgres + Redis
- Native execution for code you're actively changing

This gives you **instant hot reload** and **maximum productivity**! 🚀
