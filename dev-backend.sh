#!/bin/bash

# Quick script to run ONLY backend
# Use this if you only need to work on backend

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Starting Backend Only${NC}\n"

# Start database services if not running
if ! docker ps | grep -q leadgen-postgres-dev; then
    echo -e "${BLUE}📦 Starting database services...${NC}"
    docker-compose -f docker-compose.dev.yml up -d
    sleep 3
fi

# Activate venv and run
cd backend
source venv/bin/activate

echo -e "${GREEN}🚀 Backend running at http://localhost:8000${NC}"
echo -e "${GREEN}📚 API Docs at http://localhost:8000/docs${NC}\n"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
