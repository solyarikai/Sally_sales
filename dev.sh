#!/bin/bash

# Fast Local Development Script
# This runs frontend and backend natively for maximum speed

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Fast Local Development Environment${NC}\n"

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Start database services
echo -e "${YELLOW}📦 Starting database services (Postgres + Redis)...${NC}"
docker-compose -f docker-compose.dev.yml up -d

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 3

# Check if backend .env exists
if [ ! -f backend/.env ]; then
    echo -e "${YELLOW}⚠️  No backend/.env found. Copying from .env.dev...${NC}"
    cp backend/.env.dev backend/.env
    echo -e "${RED}⚠️  Please edit backend/.env and add your API keys!${NC}"
fi

# Check if Python venv exists
if [ ! -d backend/venv ]; then
    echo -e "${YELLOW}🐍 Creating Python virtual environment...${NC}"
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    cd ..
else
    echo -e "${GREEN}✓ Python venv exists${NC}"
fi

# Check if node_modules exists
if [ ! -d frontend/node_modules ]; then
    echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
else
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
fi

# Run migrations
echo -e "${YELLOW}🔄 Running database migrations...${NC}"
cd backend
source venv/bin/activate
alembic upgrade head
cd ..

echo -e "\n${GREEN}✅ Setup complete!${NC}\n"
echo -e "${BLUE}Starting development servers...${NC}\n"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Stopping development servers...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    docker-compose -f docker-compose.dev.yml down
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend in background
echo -e "${GREEN}🔧 Starting Backend (FastAPI)...${NC}"
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Give backend time to start
sleep 2

# Start frontend in background
echo -e "${GREEN}⚛️  Starting Frontend (Vite)...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Development environment is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo -e "${BLUE}Frontend:${NC}       http://localhost:5173"
echo -e "${BLUE}Backend API:${NC}    http://localhost:8000"
echo -e "${BLUE}API Docs:${NC}       http://localhost:8000/docs"
echo -e "${BLUE}Redis Commander:${NC} docker-compose -f docker-compose.dev.yml --profile debug up -d"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
