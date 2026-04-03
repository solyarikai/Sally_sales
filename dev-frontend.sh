#!/bin/bash

# Quick script to run ONLY frontend
# Use this if backend is already running

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}⚛️  Starting Frontend Only${NC}\n"

cd frontend

echo -e "${GREEN}🚀 Frontend running at http://localhost:5173${NC}\n"

npm run dev
