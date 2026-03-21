#!/bin/bash
# Master script: gather TAM for all EasyStaff Global cities
# Runs on Hetzner HOST (not Docker) — needs Chromium for Puppeteer
# Sequential: one Apollo session at a time

set -e
cd ~/magnum-opus-project/repo

KEYWORDS="marketing agency,digital agency,creative agency,software development,IT services,web design,app development,video production,animation studio,game studio,SaaS,fintech,media agency,branding agency,PR agency,design agency,production house,SEO agency,content agency,e-commerce,tech startup,cloud consulting,cybersecurity,data analytics,AI consulting,DevOps,mobile development"
MAX_PAGES=50

declare -A CITIES
CITIES["los_angeles"]="Los Angeles, California, United States"
CITIES["miami"]="Miami, Florida, United States"
CITIES["riyadh"]="Riyadh, Saudi Arabia"
CITIES["london"]="London, England, United Kingdom"
CITIES["singapore"]="Singapore"
CITIES["sydney"]="Sydney, New South Wales, Australia"
CITIES["austin"]="Austin, Texas, United States"
CITIES["doha"]="Doha, Qatar"
CITIES["jeddah"]="Jeddah, Saudi Arabia"
CITIES["berlin"]="Berlin, Germany"
CITIES["amsterdam"]="Amsterdam, Netherlands"

for SLUG in los_angeles miami riyadh london singapore sydney austin doha jeddah berlin amsterdam; do
    LOCATION="${CITIES[$SLUG]}"
    OUT_DIR="gathering-data/$SLUG"
    OUT_FILE="${SLUG}_companies.json"
    LOG="/tmp/apollo_${SLUG}.log"

    # Skip if already gathered
    if [ -f "$OUT_DIR/$OUT_FILE" ]; then
        COUNT=$(python3 -c "import json; print(len(json.load(open('$OUT_DIR/$OUT_FILE'))))" 2>/dev/null || echo 0)
        if [ "$COUNT" -gt 100 ]; then
            echo "=== SKIP $SLUG: already has $COUNT companies ==="
            continue
        fi
    fi

    echo "=== GATHERING: $SLUG ($LOCATION) ==="
    mkdir -p "$OUT_DIR"

    node scripts/apollo_universal_search.js \
        --location "$LOCATION" \
        --keywords "$KEYWORDS" \
        --sizes "1,10" --sizes "11,50" --sizes "51,200" \
        --max-pages $MAX_PAGES \
        --output-dir "$OUT_DIR" \
        --output-file "$OUT_FILE" \
        2>&1 | tee "$LOG"

    # Count results
    if [ -f "$OUT_DIR/$OUT_FILE" ]; then
        COUNT=$(python3 -c "import json; print(len(json.load(open('$OUT_DIR/$OUT_FILE'))))")
        echo "=== DONE: $SLUG — $COUNT companies ==="
    else
        echo "=== FAILED: $SLUG — no output file ==="
    fi

    echo ""
    sleep 10  # Cool down between cities
done

echo "=== ALL CITIES COMPLETE ==="
ls -la gathering-data/*/
