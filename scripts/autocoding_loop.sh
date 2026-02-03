#!/bin/bash
# Autocoding Loop - Continuous CRM improvement
# Runs every 5 minutes, checks system health, triggers fixes

LOG_FILE="/home/leadokol/logs/autocoding.log"
mkdir -p /home/leadokol/logs

log() {
    echo "$(date -Iseconds) | $1" >> $LOG_FILE
}

check_and_fix() {
    log "=== Starting autocoding check ==="
    
    # 1. Check backend health
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
    if [ -z "$HEALTH" ]; then
        log "ERROR: Backend not responding, restarting..."
        cd ~/magnum-opus-project/repo && docker-compose restart backend 2>/dev/null
        sleep 30
    else
        log "OK: Backend healthy"
    fi
    
    # 2. Check frontend
    FRONTEND=$(curl -s http://localhost:80/ 2>/dev/null | head -1)
    if [ -z "$FRONTEND" ]; then
        log "ERROR: Frontend not responding, restarting..."
        cd ~/magnum-opus-project/repo && docker-compose restart frontend 2>/dev/null
        sleep 10
    else
        log "OK: Frontend healthy"
    fi
    
    # 3. Get sync status
    STATUS=$(curl -s -H "X-Company-ID: 1" http://localhost:8000/api/crm-sync/status 2>/dev/null)
    TOTAL=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_contacts', 0))" 2>/dev/null)
    REPLIED=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('replied_contacts', 0))" 2>/dev/null)
    log "STATUS: $TOTAL contacts, $REPLIED replied"
    
    # 4. Check for errors in backend logs
    ERRORS=$(docker logs leadgen-backend --since 5m 2>&1 | grep -c "ERROR\|Exception" || echo 0)
    if [ "$ERRORS" -gt 5 ]; then
        log "WARNING: $ERRORS errors in last 5 minutes"
    fi
    
    # 5. Test API endpoints
    CONTACTS_OK=$(curl -s "http://localhost:8000/api/contacts?limit=1" 2>/dev/null | grep -c '"contacts"' || echo 0)
    if [ "$CONTACTS_OK" -eq 0 ]; then
        log "ERROR: Contacts API not working"
    else
        log "OK: Contacts API working"
    fi
    
    log "=== Check complete ==="
}

# Run once
check_and_fix
