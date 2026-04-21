#!/bin/bash
# Run findymail step for 4 segments with --no-upload (skip SmartLead).
# Uses CSVs produced by exa-lookup step.
set -e

cd ~/magnum-opus-project/repo
set -a && source .env && set +a

DATE=2026-04-17
BASE=sofia/scripts/output/OnSocial/pipeline

for SEG in IMAGENCY INFPLAT SOCCOM AFFPERF; do
    seg_lower=$(echo $SEG | tr '[:upper:]' '[:lower:]')
    csv_path="$BASE/apollo_people_${SEG}_${DATE}_exa.csv"

    if [ ! -f "$csv_path" ]; then
        echo "SKIP $SEG (no $csv_path)"
        continue
    fi

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  FindyMail — $SEG"
    echo "════════════════════════════════════════════════════════════"

    python3 sofia/scripts/bace/pipeline.py people \
        --from-step findymail \
        --csv "$csv_path" \
        --segment "$seg_lower" \
        --project-id 42 \
        --no-upload \
        --auto-approve 2>&1

    echo "✓ $SEG done"
done

echo ""
echo "=== ALL FINDYMAIL DONE ==="
