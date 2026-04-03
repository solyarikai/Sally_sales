#!/bin/bash
# Enrich Contacts Pipeline
#
# Takes CSV with name + company → outputs CSV with emails
#
# Steps:
#   1. Apollo Person Lookup (FREE) → LinkedIn URLs
#   2. Clay + FindyMail (PAID: $0.01/email) → Emails
#
# Usage:
#   bash scripts/enrich_contacts_pipeline.sh input.csv
#   bash scripts/enrich_contacts_pipeline.sh input.csv --name-col "name" --company-col "company"
#   bash scripts/enrich_contacts_pipeline.sh input.csv --skip-apollo  # if already has LinkedIn
#   bash scripts/enrich_contacts_pipeline.sh input.csv --limit 10     # test run

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_FILE="$1"
shift || true

# Parse args
NAME_COL="name"
COMPANY_COL="company"
LINKEDIN_COL="linkedin_url"
SKIP_APOLLO=false
LIMIT=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --name-col) NAME_COL="$2"; shift 2 ;;
    --company-col) COMPANY_COL="$2"; shift 2 ;;
    --linkedin-col) LINKEDIN_COL="$2"; shift 2 ;;
    --skip-apollo) SKIP_APOLLO=true; shift ;;
    --limit) LIMIT="--limit $2"; shift 2 ;;
    *) shift ;;
  esac
done

if [ -z "$INPUT_FILE" ]; then
  echo "Usage: bash enrich_contacts_pipeline.sh input.csv [options]"
  echo ""
  echo "Options:"
  echo "  --name-col NAME       Column with person name (default: name)"
  echo "  --company-col NAME    Column with company name (default: company)"
  echo "  --linkedin-col NAME   Column with LinkedIn URL (default: linkedin_url)"
  echo "  --skip-apollo         Skip Apollo step (use if already have LinkedIn URLs)"
  echo "  --limit N             Process only N rows (for testing)"
  echo ""
  echo "Pipeline:"
  echo "  1. Apollo People Search (FREE) → finds LinkedIn URLs"
  echo "  2. Clay + FindyMail (\$0.01/email) → finds emails"
  exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
  echo "ERROR: File not found: $INPUT_FILE"
  exit 1
fi

BASENAME=$(basename "$INPUT_FILE" .csv)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WORK_DIR="$SCRIPT_DIR/exports/enrich_${BASENAME}_${TIMESTAMP}"
mkdir -p "$WORK_DIR"

echo "=== Enrich Contacts Pipeline ==="
echo "Input: $INPUT_FILE"
echo "Work dir: $WORK_DIR"
echo ""

# Step 1: Apollo Person Lookup
APOLLO_OUTPUT="$WORK_DIR/01_apollo_linkedin.csv"

if [ "$SKIP_APOLLO" = true ]; then
  echo "[1/2] SKIP Apollo (--skip-apollo flag)"
  cp "$INPUT_FILE" "$APOLLO_OUTPUT"
else
  echo "[1/2] Apollo Person Lookup → LinkedIn URLs"
  node apollo_person_lookup.js \
    --file "$INPUT_FILE" \
    --name-col "$NAME_COL" \
    --company-col "$COMPANY_COL" \
    --output "$APOLLO_OUTPUT" \
    --headless \
    $LIMIT

  # Count results
  TOTAL=$(wc -l < "$APOLLO_OUTPUT")
  FOUND=$(grep -c "linkedin.com" "$APOLLO_OUTPUT" || echo 0)
  echo "  LinkedIn found: $FOUND / $((TOTAL - 1))"
fi

# Check if we have LinkedIn URLs to enrich
LINKEDIN_COUNT=$(grep -c "linkedin.com" "$APOLLO_OUTPUT" || echo 0)
if [ "$LINKEDIN_COUNT" -eq 0 ]; then
  echo ""
  echo "No LinkedIn URLs found. Cannot proceed to FindyMail."
  echo "Output (no emails): $APOLLO_OUTPUT"
  exit 0
fi

# Step 2: Clay + FindyMail
echo ""
echo "[2/2] Clay + FindyMail → Emails"
echo "  Contacts with LinkedIn: $LINKEDIN_COUNT"
echo "  Estimated cost: \$$(echo "scale=2; $LINKEDIN_COUNT * 0.01" | bc)"
echo ""
read -p "Proceed with FindyMail enrichment? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  FINAL_OUTPUT="$WORK_DIR/02_final_with_emails.json"

  cd "$SCRIPT_DIR/clay"
  node clay_enrich.js \
    --file "$APOLLO_OUTPUT" \
    --linkedin-col "$LINKEDIN_COL" \
    --enrich findymail \
    --output "$FINAL_OUTPUT" \
    --headless \
    --auto

  echo ""
  echo "=== DONE ==="
  echo "Final output: $FINAL_OUTPUT"
else
  echo "Skipped FindyMail. LinkedIn data saved to: $APOLLO_OUTPUT"
fi
