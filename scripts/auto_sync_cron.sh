#!/bin/bash
# CRM Auto Sync - Runs every 5 minutes via cron
# Add to crontab: */5 * * * * /home/leadokol/magnum-opus-project/repo/scripts/auto_sync_cron.sh

LOG_FILE="/home/leadokol/logs/crm_auto_sync.log"
mkdir -p /home/leadokol/logs

TIMESTAMP=$(date -Iseconds)

# Trigger sync via API with proper JSON body and headers
RESULT=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: 1" \
  -d '{"sources": ["smartlead", "getsales"], "full_sync": false}' \
  "http://localhost:8000/api/crm-sync/trigger" 2>/dev/null)

if [ -n "$RESULT" ]; then
    echo "$TIMESTAMP | SYNC | $RESULT" >> $LOG_FILE
else
    echo "$TIMESTAMP | ERROR | Backend not responding" >> $LOG_FILE
fi
