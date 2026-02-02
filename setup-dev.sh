#!/bin/bash

# One-time setup script for fast local development
# Run this once, then use ./dev.sh for daily development

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Fast Local Development - Initial Setup       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}\n"

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}\n"

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓ Python: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python 3.11+ is required but not found${NC}"
    exit 1
fi

# Check Node
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓ Node.js: $NODE_VERSION${NC}"
else
    echo -e "${RED}✗ Node.js 18+ is required but not found${NC}"
    exit 1
fi

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    echo -e "${GREEN}✓ Docker: $DOCKER_VERSION${NC}"
else
    echo -e "${RED}✗ Docker is required but not found${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Docker is running${NC}"
fi

echo ""

# Setup backend .env
echo -e "${YELLOW}🔧 Setting up backend environment...${NC}"
if [ ! -f backend/.env ]; then
    cp backend/.env.dev backend/.env
    echo -e "${GREEN}✓ Created backend/.env from template${NC}"
    echo -e "${YELLOW}⚠️  Please edit backend/.env and add your API keys!${NC}"
    NEED_API_KEYS=true
else
    echo -e "${GREEN}✓ backend/.env already exists${NC}"
fi

# Create Python venv
echo -e "\n${YELLOW}🐍 Setting up Python virtual environment...${NC}"
if [ ! -d backend/venv ]; then
    cd backend
    python3 -m venv venv
    echo -e "${GREEN}✓ Created Python virtual environment${NC}"
    
    source venv/bin/activate
    echo -e "${YELLOW}📦 Installing Python dependencies (this may take a minute)...${NC}"
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}✓ Installed Python dependencies${NC}"
    cd ..
else
    echo -e "${GREEN}✓ Python venv already exists${NC}"
    
    # Check if we need to update dependencies
    cd backend
    source venv/bin/activate
    if ! pip show fastapi > /dev/null 2>&1; then
        echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"
        pip install -r requirements.txt --quiet
        echo -e "${GREEN}✓ Installed Python dependencies${NC}"
    fi
    cd ..
fi

# Install frontend dependencies
echo -e "\n${YELLOW}⚛️  Setting up frontend...${NC}"
if [ ! -d frontend/node_modules ]; then
    cd frontend
    echo -e "${YELLOW}📦 Installing frontend dependencies (this may take a minute)...${NC}"
    npm install --silent
    echo -e "${GREEN}✓ Installed frontend dependencies${NC}"
    cd ..
else
    echo -e "${GREEN}✓ Frontend dependencies already installed${NC}"
fi

# Start database services
echo -e "\n${YELLOW}🐘 Starting database services...${NC}"
docker-compose -f docker-compose.dev.yml up -d

echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Check if services are healthy
if docker ps | grep -q leadgen-postgres-dev; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL failed to start${NC}"
    exit 1
fi

if docker ps | grep -q leadgen-redis-dev; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${RED}✗ Redis failed to start${NC}"
    exit 1
fi

# Run migrations
echo -e "\n${YELLOW}🔄 Running database migrations...${NC}"
cd backend
source venv/bin/activate
alembic upgrade head
echo -e "${GREEN}✓ Database migrations complete${NC}"
cd ..

# Make dev scripts executable
chmod +x dev.sh dev-backend.sh dev-frontend.sh

echo -e "\n${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Setup Complete! 🎉                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}\n"

if [ "$NEED_API_KEYS" = true ]; then
    echo -e "${YELLOW}⚠️  IMPORTANT: Before you start developing:${NC}"
    echo -e "${YELLOW}   1. Edit backend/.env${NC}"
    echo -e "${YELLOW}   2. Add your OPENAI_API_KEY and other API keys${NC}"
    echo -e "${YELLOW}   3. Then run: ./dev.sh${NC}\n"
else
    echo -e "${GREEN}Ready to start developing!${NC}\n"
    echo -e "${BLUE}Run this command to start development:${NC}"
    echo -e "${GREEN}   ./dev.sh${NC}\n"
fi

echo -e "${BLUE}Quick commands:${NC}"
echo -e "  ${GREEN}./dev.sh${NC}          - Start full development environment"
echo -e "  ${GREEN}./dev-backend.sh${NC}  - Start backend only"
echo -e "  ${GREEN}./dev-frontend.sh${NC} - Start frontend only"
echo -e ""
echo -e "${BLUE}Documentation:${NC}"
echo -e "  ${GREEN}QUICK_START.md${NC}        - Quick start guide"
echo -e "  ${GREEN}DEV_GUIDE.md${NC}          - Detailed development guide"
echo -e "  ${GREEN}DOCKER_VS_NATIVE.md${NC}   - Speed comparison & benchmarks"
echo -e ""
