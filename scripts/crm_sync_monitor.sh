#!/bin/bash
# CRM Sync Monitor - Logs contact counts every minute
# Log file: /home/leadokol/logs/crm_sync_progress.log

LOG_FILE="/home/leadokol/logs/crm_sync_progress.log"
mkdir -p /home/leadokol/logs

while true; do
    TIMESTAMP=$(date -Iseconds)
    STATUS=$(curl -s -H "X-Company-ID: 1" "http://localhost:8000/api/crm-sync/status" 2>/dev/null)
    
    if [ -n "$STATUS" ]; then
        TOTAL=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_contacts', 0))" 2>/dev/null)
        GETSALES=$(echo $STATUS | python3 -c "import sys,json; d=json.load(sys.stdin).get('by_source',{}); print(d.get('getsales',0))" 2>/dev/null)
        SMARTLEAD=$(echo $STATUS | python3 -c "import sys,json; d=json.load(sys.stdin).get('by_source',{}); print(d.get('smartlead',0))" 2>/dev/null)
        MERGED_GS=$(echo $STATUS | python3 -c "import sys,json; d=json.load(sys.stdin).get('by_source',{}); print(d.get('getsales+smartlead',0))" 2>/dev/null)
        MERGED_SG=$(echo $STATUS | python3 -c "import sys,json; d=json.load(sys.stdin).get('by_source',{}); print(d.get('smartlead+getsales',0))" 2>/dev/null)
        MERGED=$((MERGED_GS + MERGED_SG))
        
        echo "$TIMESTAMP | total=$TOTAL | smartlead=$SMARTLEAD | getsales=$GETSALES | merged=$MERGED" >> $LOG_FILE
        echo "$TIMESTAMP | total=$TOTAL | smartlead=$SMARTLEAD | getsales=$GETSALES | merged=$MERGED"
    else
        echo "$TIMESTAMP | ERROR: Backend not responding" >> $LOG_FILE
    fi
    
    sleep 60
done
