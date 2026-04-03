#!/bin/bash
# Run both enrichment scripts in background
# Usage: ./run_enrichment.sh

cd ~/magnum-opus-project/repo

echo "Starting enrichment scripts..."
echo "Logs: /tmp/enrich_getsales_flows.log, /tmp/enrich_smartlead_campaigns.log"

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run GetSales enrichment
echo "Starting GetSales flow enrichment..."
nohup python3 scripts/enrich_getsales_flows.py > /tmp/enrich_getsales_flows.log 2>&1 &
GETSALES_PID=$!
echo "GetSales PID: $GETSALES_PID"

# Run Smartlead enrichment
echo "Starting Smartlead campaign enrichment..."
nohup python3 scripts/enrich_smartlead_campaigns.py > /tmp/enrich_smartlead_campaigns.log 2>&1 &
SMARTLEAD_PID=$!
echo "Smartlead PID: $SMARTLEAD_PID"

# Save PIDs
echo "$GETSALES_PID" > /tmp/enrich_getsales.pid
echo "$SMARTLEAD_PID" > /tmp/enrich_smartlead.pid

echo ""
echo "Both scripts running in background."
echo "Monitor progress:"
echo "  tail -f /tmp/enrich_getsales_flows.log"
echo "  tail -f /tmp/enrich_smartlead_campaigns.log"
echo ""
echo "Stop scripts:"
echo "  kill \$(cat /tmp/enrich_getsales.pid)"
echo "  kill \$(cat /tmp/enrich_smartlead.pid)"
