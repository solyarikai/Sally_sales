#!/bin/bash
# Deploy script: stops pipeline, rebuilds, restarts pipeline
# Usage: ssh hetzner 'bash ~/magnum-opus-project/repo/scripts/deploy.sh'
set -e

REPO_DIR=~/magnum-opus-project/repo
API_URL="http://localhost:8000/api"
HEADER="-H X-Company-ID:1"

echo "=== Deploy started at $(date) ==="

# 1. Check if pipeline is running, stop it if so
echo ">> Checking pipeline status..."
PIPELINE_STATUS=$(curl -s "$API_URL/pipeline/full-pipeline/18/status" $HEADER 2>/dev/null || echo '{"status":"unknown"}')
IS_RUNNING=$(echo "$PIPELINE_STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('running', False))" 2>/dev/null || echo "False")

PIPELINE_WAS_RUNNING=false
if [ "$IS_RUNNING" = "True" ]; then
    echo ">> Pipeline is running — stopping it..."
    curl -s -X POST "$API_URL/pipeline/full-pipeline/18/stop" $HEADER > /dev/null 2>&1 || true
    PIPELINE_WAS_RUNNING=true
    sleep 3
    echo ">> Pipeline stopped."
else
    echo ">> Pipeline not running."
fi

# 2. Code is pushed directly via 'git push server main' — no pull needed
echo ">> Code already up to date (pushed via git remote)"
cd "$REPO_DIR"

# 3. Rebuild and restart containers
echo ">> Rebuilding containers..."
docker-compose up --build -d 2>&1

# 4. Wait for backend to be healthy
echo ">> Waiting for backend health..."
for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo ">> Backend healthy after ${i}s"
        break
    fi
    sleep 1
done

# 5. Restart pipeline if it was running
if [ "$PIPELINE_WAS_RUNNING" = "true" ]; then
    echo ">> Restarting pipeline (was running before deploy)..."
    curl -s -X POST "$API_URL/pipeline/full-pipeline/18" \
        $HEADER \
        -H 'Content-Type: application/json' \
        -d '{"max_queries": 1500, "target_goal": 2000, "apollo_search": false, "skip_smartlead_push": true}' \
        > /dev/null 2>&1 || true
    echo ">> Pipeline restarted."
fi

echo "=== Deploy finished at $(date) ==="
