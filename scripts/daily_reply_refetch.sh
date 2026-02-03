#!/bin/bash
# Daily Reply Refetch - Syncs replies from Smartlead
# Run once a day at 2 AM: 0 2 * * * /path/to/daily_reply_refetch.sh

LOG_FILE="/home/leadokol/logs/reply_refetch.log"
mkdir -p /home/leadokol/logs

log() {
    echo "$(date -Iseconds) | $1" >> $LOG_FILE
}

log "=== Starting daily reply refetch ==="

# 1. Fetch replies from Smartlead campaigns
log "Fetching Smartlead replies..."
RESULT=$(curl -s -X POST -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/fetch-replies" 2>/dev/null)
log "Result: $RESULT"

# 2. Wait for fetch to complete
sleep 180

# 3. Check how many replied contacts
STATUS=$(curl -s -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/status" 2>/dev/null)
REPLIED=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('replied_contacts', 0))" 2>/dev/null)
TOTAL=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_contacts', 0))" 2>/dev/null)
log "Status: $TOTAL contacts, $REPLIED replied"

log "=== Daily reply refetch complete ==="
