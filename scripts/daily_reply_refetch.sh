#!/bin/bash
# Daily Reply Refetch - Syncs replies from Smartlead and GetSales
# Run once a day at 2 AM: 0 2 * * * /path/to/daily_reply_refetch.sh

LOG_FILE="/home/leadokol/logs/reply_refetch.log"
mkdir -p /home/leadokol/logs

log() {
    echo "$(date -Iseconds) | $1" >> $LOG_FILE
}

log "=== Starting daily reply refetch ==="

# 1. Fetch replies from Smartlead campaigns (via API endpoint)
log "Fetching Smartlead replies via API..."
RESULT=$(curl -s -X POST -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/fetch-replies" 2>/dev/null)
log "Smartlead Result: $RESULT"

# Wait for Smartlead fetch
sleep 120

# 2. Fetch replies from GetSales (via script in Docker)
log "Fetching GetSales replies..."
docker exec -e DATABASE_URL="postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen" \
    leadgen-backend python3 /app/scripts/fetch_getsales_replies.py >> $LOG_FILE 2>&1
log "GetSales reply fetch complete"

# 3. Check status
sleep 10
STATUS=$(curl -s -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/status" 2>/dev/null)
REPLIED=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('replied_contacts', 0))" 2>/dev/null)
TOTAL=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_contacts', 0))" 2>/dev/null)
ACTIVITIES=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_activities', 0))" 2>/dev/null)
log "Status: $TOTAL contacts, $REPLIED replied, $ACTIVITIES activities"

log "=== Daily reply refetch complete ==="
