# Quick Start - Fast Local Development

## 🚀 Fastest Way to Start Developing

```bash
# One command to rule them all
./dev.sh
```

That's it! This will:
1. ✅ Start Postgres + Redis in Docker
2. ✅ Setup Python virtual environment (if needed)
3. ✅ Install all dependencies (if needed)
4. ✅ Run database migrations
5. ✅ Start backend with hot reload
6. ✅ Start frontend with hot reload

**Access your app:**
- 🌐 Frontend: http://localhost:5173
- ⚡ Backend API: http://localhost:8000
- 📚 API Docs: http://localhost:8000/docs

## ⚡ Why This Is Fast

Traditional Docker development:
- Change code → Wait 5 seconds → See result
- Add dependency → Rebuild → Wait 2-5 minutes

**This setup:**
- Change code → See result in 0.1 seconds ⚡
- Add dependency → Install → Wait 5-10 seconds ⚡

**20-50x faster!** See [DOCKER_VS_NATIVE.md](./DOCKER_VS_NATIVE.md) for benchmarks.

## 🎯 Common Workflows

### Working on Backend Only
```bash
./dev-backend.sh
```

### Working on Frontend Only
```bash
./dev-frontend.sh
```

### Full Development (Both)
```bash
./dev.sh
```

### Production Build (Testing)
```bash
docker-compose up -d --build
```

## 📝 First Time Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker Desktop

### Configuration

1. **Copy environment file:**
```bash
cp backend/.env.dev backend/.env
```

2. **Add your API keys to `backend/.env`:**
```env
OPENAI_API_KEY=sk-your-key-here
SMARTLEAD_API_KEY=your-key-here
# ... other keys
```

3. **Run the dev script:**
```bash
./dev.sh
```

That's it! 🎉

## 🔧 Development Tips

### Hot Reload
- **Frontend**: Edit any `.tsx` file → Browser updates instantly
- **Backend**: Edit any `.py` file → API reloads in 0.5s

### Database Changes
```bash
cd backend
source venv/bin/activate
alembic revision --autogenerate -m "Add new field"
alembic upgrade head
```

### Add Python Package
```bash
cd backend
source venv/bin/activate
pip install package-name
pip freeze > requirements.txt
```

### Add NPM Package
```bash
cd frontend
npm install package-name
```

### View Logs
- **Backend**: Check terminal where `dev.sh` is running
- **Frontend**: Check terminal or browser console
- **Database**: `docker logs leadgen-postgres-dev`

### Database Access
```bash
# CLI
docker exec -it leadgen-postgres-dev psql -U leadgen -d leadgen

# Or use GUI tools (pgAdmin, DBeaver, TablePlus)
# Host: localhost:5432
# User: leadgen
# Password: leadgen_secret
# Database: leadgen
```

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Kill backend (port 8000)
lsof -ti:8000 | xargs kill -9

# Kill frontend (port 5173)
lsof -ti:5173 | xargs kill -9
```

### Database Connection Error
```bash
docker-compose -f docker-compose.dev.yml restart
```

### Start Fresh
```bash
# Stop everything
docker-compose -f docker-compose.dev.yml down -v

# Start again
./dev.sh
```

## 📚 Documentation

- **[DEV_GUIDE.md](./DEV_GUIDE.md)** - Detailed development guide
- **[DOCKER_VS_NATIVE.md](./DOCKER_VS_NATIVE.md)** - Speed comparison & benchmarks
- **[README.md](./README.md)** - Full project documentation

## 🎯 Summary

**For daily development:**
```bash
./dev.sh  # Start everything fast
```

**For production:**
```bash
docker-compose up -d --build  # Full Docker deployment
```

**Result:** Maximum development speed with production-ready deployment! 🚀
