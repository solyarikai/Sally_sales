#!/bin/bash

# Sync CRM - Fetch and merge contacts from Smartlead and GetSales

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          CRM Sync - Smartlead + GetSales       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}\n"

# Change to scripts directory
cd "$(dirname "$0")"

# Set API keys from environment or use defaults
export SMARTLEAD_API_KEY="${SMARTLEAD_API_KEY:-eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5}"
export GETSALES_API_KEY="${GETSALES_API_KEY:-eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc}"

# Step 1: Fetch Smartlead contacts
echo -e "${YELLOW}Step 1/4: Fetching Smartlead contacts...${NC}"
python3 fetch_smartlead_contacts.py
echo ""

# Step 2: Fetch GetSales contacts
echo -e "${YELLOW}Step 2/4: Fetching GetSales contacts...${NC}"
python3 fetch_getsales_contacts.py
echo ""

# Step 3: Merge contacts
echo -e "${YELLOW}Step 3/4: Merging contacts...${NC}"
python3 merge_contacts.py
echo ""

# Step 4: Import to database (if backend is running)
echo -e "${YELLOW}Step 4/4: Importing to database...${NC}"
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "Backend is running, importing contacts..."
    
    # Get the merged contacts as a JSON array
    CONTACTS_JSON=$(cat merged_contacts.json)
    
    # Import to database with company ID header
    curl -X POST http://localhost:8000/api/contacts/import/merged \
        -H "Content-Type: application/json" \
        -H "X-Company-ID: 1" \
        -d "$CONTACTS_JSON"
    echo ""
else
    echo -e "${YELLOW}Backend not running. Skipping database import.${NC}"
    echo -e "${YELLOW}Run './dev.sh' to start the backend, then import manually.${NC}"
fi

echo -e "\n${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              CRM Sync Complete! 🎉             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}\n"

echo -e "${BLUE}Files created:${NC}"
echo -e "  - smartlead_contacts.json"
echo -e "  - getsales_contacts.json"
echo -e "  - merged_contacts.json"
echo ""
