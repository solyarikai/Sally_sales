#!/bin/bash
# =================================================================
# Overseas DM Pipeline — Single Command Runner
#
# Runs the ENTIRE pipeline for a US state:
# 1. TAM company search (Clay Puppeteer)
# 2. Overseas employee search (Clay Puppeteer)
# 3. Analyze overseas workers (Python)
# 4. Decision maker search (Clay Puppeteer)
# 5. Filter DMs to companies with overseas employees
# 6. FindyMail email enrichment (API)
# 7. Build final XLSX
#
# Usage:
#   ./run_overseas_pipeline.sh Missouri
#   ./run_overseas_pipeline.sh Texas
#   ./run_overseas_pipeline.sh Ohio
#
# Prerequisites:
#   - Clay session cookie set in clay_session.json on Hetzner
#   - git pull done on Hetzner
#
# Cost: 0 Clay credits + ~1 FindyMail credit per DM
# =================================================================

set -e

STATE="$1"
if [ -z "$STATE" ]; then
    echo "Usage: ./run_overseas_pipeline.sh STATE_NAME"
    echo "Example: ./run_overseas_pipeline.sh Missouri"
    exit 1
fi

STATE_LOWER=$(echo "$STATE" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPORTS_DIR="$SCRIPT_DIR/exports"
HETZNER_REPO="~/magnum-opus-project/repo"
TITLES='["HR","CEO","COO","Payroll","Founder","Accountant","Finance","CFO","Head of HR","Human Resources","Controller"]'

echo ""
echo "=========================================="
echo "  Overseas DM Pipeline: $STATE"
echo "=========================================="
echo ""

# --- Step 0: Validate prerequisites ---
echo "[0] Validating prerequisites..."
ssh hetzner "cat $HETZNER_REPO/scripts/clay/clay_session.json" > /dev/null 2>&1 || {
    echo "ERROR: Clay session cookie not found on Hetzner."
    echo "Set it: ssh hetzner \"echo '{\\\"value\\\":\\\"COOKIE\\\",\\\"savedAt\\\":\\\"...\\\"}' > $HETZNER_REPO/scripts/clay/clay_session.json\""
    exit 1
}
echo "  Cookie exists on Hetzner"

ssh hetzner "cd $HETZNER_REPO && git pull origin main" 2>&1 | tail -3
echo "  Code up to date"
echo ""

# --- Step 1: TAM Company Search ---
echo "[1] TAM Company Search for $STATE..."
ssh hetzner "cd $HETZNER_REPO && node scripts/clay/clay_tam_export.js \
    --load-search 'All_remote_friendly' \
    --state '$STATE' \
    --headless --auto" 2>&1 | tee /tmp/pipeline_step1.log | tail -5

# Extract table ID
TABLE_ID=$(ssh hetzner "cat $HETZNER_REPO/scripts/clay/exports/tam_results.json 2>/dev/null" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tableId',''))" 2>/dev/null)
if [ -z "$TABLE_ID" ]; then
    echo "ERROR: No table ID found from TAM search"
    exit 1
fi
echo "  Table ID: $TABLE_ID"
echo ""

# --- Step 2: Find Overseas Employees ---
echo "[2] Finding overseas employees (excluding US)..."
ssh hetzner "cd $HETZNER_REPO && node scripts/clay/clay_people_search.js \
    --table-id $TABLE_ID \
    --countries-exclude 'United States' \
    --headless --auto" 2>&1 | tee /tmp/pipeline_step2.log | tail -5

# Download results
echo "  Downloading overseas employee data..."
scp hetzner:$HETZNER_REPO/scripts/clay/exports/people_enrichment.json /tmp/overseas_employees.json
OVERSEAS_COUNT=$(python3 -c "import json; print(len(json.load(open('/tmp/overseas_employees.json'))))")
echo "  Overseas employees found: $OVERSEAS_COUNT"
echo ""

# --- Step 3: Analyze Overseas Workers ---
echo "[3] Analyzing overseas workers per company..."
python3 "$SCRIPT_DIR/analyze_overseas.py" \
    --input /tmp/overseas_employees.json \
    --state "$STATE" \
    --output /tmp/
OVERSEAS_CSV="/tmp/${STATE_LOWER}_overseas_workers.csv"
COMPANY_COUNT=$(python3 -c "import csv; print(sum(1 for _ in csv.DictReader(open('$OVERSEAS_CSV'))))")
echo "  Companies with overseas employees: $COMPANY_COUNT"
echo ""

# --- Step 4: Find Decision Makers ---
echo "[4] Finding decision makers (HR, CEO, Finance, etc.)..."
ssh hetzner "cd $HETZNER_REPO && \
    CLAY_CUSTOM_TITLES='$TITLES' \
    node scripts/clay/clay_people_search.js \
    --table-id $TABLE_ID \
    --countries-exclude NONE \
    --headless --auto" 2>&1 | tee /tmp/pipeline_step4.log | tail -5

# Download results
echo "  Downloading decision maker data..."
scp hetzner:$HETZNER_REPO/scripts/clay/exports/people_enrichment.json /tmp/dm_people_all.json
DM_ALL_COUNT=$(python3 -c "import json; print(len(json.load(open('/tmp/dm_people_all.json'))))")
echo "  Total DMs found: $DM_ALL_COUNT"
echo ""

# --- Step 5: Filter DMs to companies with overseas employees ---
echo "[5] Filtering DMs to companies with overseas employees (max 4/company)..."
python3 << PYEOF
import json, csv, re

def normalize_domain(d):
    if not d: return ''
    d = d.lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')

companies = set()
with open('$OVERSEAS_CSV') as f:
    for row in csv.DictReader(f):
        companies.add(normalize_domain(row.get('Domain', '')))

with open('/tmp/dm_people_all.json') as f:
    all_people = json.load(f)

matched = []
counts = {}
for p in all_people:
    domain = normalize_domain(p.get('Company Domain', ''))
    if domain not in companies: continue
    counts[domain] = counts.get(domain, 0) + 1
    if counts[domain] <= 4:
        matched.append(p)

with open('/tmp/dm_filtered.json', 'w') as f:
    json.dump(matched, f, indent=2)
print(f'  Filtered: {len(matched)} DMs at {len(set(counts.keys()))} companies')
PYEOF

# Upload to Hetzner for FindyMail
scp /tmp/dm_filtered.json hetzner:$HETZNER_REPO/scripts/clay/exports/dm_people.json
echo ""

# --- Step 6: FindyMail Email Enrichment ---
echo "[6] FindyMail email enrichment..."
ssh hetzner "cd $HETZNER_REPO && python3 scripts/clay/findymail_enrich_dm.py" 2>&1 | tee /tmp/pipeline_step6.log | tail -5

# Download enriched data
scp hetzner:$HETZNER_REPO/scripts/clay/exports/dm_people_with_emails.json /tmp/dm_people_with_emails.json
EMAIL_COUNT=$(python3 -c "import json; d=json.load(open('/tmp/dm_people_with_emails.json')); print(sum(1 for p in d if p.get('Email')))")
TOTAL_DM=$(python3 -c "import json; print(len(json.load(open('/tmp/dm_people_with_emails.json'))))")
echo "  Emails found: $EMAIL_COUNT / $TOTAL_DM"
echo ""

# --- Step 7: Build Final XLSX ---
echo "[7] Building final XLSX report..."
OUTPUT_FILE="$HOME/Downloads/${STATE}_DM_Report.xlsx"
python3 "$SCRIPT_DIR/build_overseas_xlsx.py" \
    --companies "$OVERSEAS_CSV" \
    --people /tmp/dm_people_with_emails.json \
    --output "$OUTPUT_FILE"

echo ""
echo "=========================================="
echo "  Pipeline Complete: $STATE"
echo "=========================================="
echo ""
echo "  Companies with overseas employees: $COMPANY_COUNT"
echo "  Decision makers found: $TOTAL_DM"
echo "  Emails found: $EMAIL_COUNT"
echo "  Report: $OUTPUT_FILE"
echo ""
echo "  Cost: 0 Clay credits + FindyMail credits for $TOTAL_DM emails"
echo "=========================================="
