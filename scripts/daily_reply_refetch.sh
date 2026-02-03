#!/bin/bash
# Daily Reply Refetch - Syncs replies from Smartlead and GetSales
# Run once a day at 2 AM: 0 2 * * * /path/to/daily_reply_refetch.sh

LOG_FILE="/home/leadokol/logs/reply_refetch.log"
mkdir -p /home/leadokol/logs

log() {
    echo "$(date -Iseconds) | $1" >> $LOG_FILE
    echo "$(date -Iseconds) | $1"
}

log "=== Starting daily reply refetch ==="

# 1. Trigger full sync with focus on replies
log "Triggering full sync..."
RESULT=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Company-ID: 1" \
    -d '{"sources": ["smartlead", "getsales"], "full_sync": true}' \
    "http://localhost:8000/api/crm-sync/trigger" 2>/dev/null)
log "Sync result: $RESULT"

# 2. Wait for sync to complete (check status periodically)
for i in {1..60}; do
    sleep 10
    STATUS=$(curl -s -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/status" 2>/dev/null)
    REPLIED=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('replied_contacts', 0))" 2>/dev/null)
    TOTAL=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_contacts', 0))" 2>/dev/null)
    log "Progress: $TOTAL contacts, $REPLIED replied"
done

# 3. Final status
STATUS=$(curl -s -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/status" 2>/dev/null)
log "Final status: $STATUS"

log "=== Daily reply refetch complete ==="
