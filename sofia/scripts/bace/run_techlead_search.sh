#!/bin/bash
# Apollo People Search — techlead only, no FindyMail
# Запуск: bash run_techlead_search.sh [imagency|infplat|soccom|affperf|all]
set -e

SEGMENT="${1:-all}"
TODAY=$(date +%Y-%m-%d)
HETZNER="hetzner"
REMOTE_REPO="~/magnum-opus-project/repo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOFIA_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
INPUT_DIR="$SOFIA_DIR/input"

TECHLEAD_TITLES="CTO,Chief Technology Officer,VP Engineering,VP of Engineering,VP Technology,VP of Technology,Head of Engineering,Head of Technology,Director of Engineering,Director of Technology,Technical Director,Technology Director,Tech Lead,Technical Lead,Lead Engineer,Engineering Lead,Chief Architect,VP Platform,Head of Platform,VP Data,Head of Data,Director of Engineering"
SENIORITIES="c_suite,vp,head,director"

echo "═══════════════════════════════════════════════════════════"
echo "  Apollo Techlead Search — $TODAY"
echo "  Segment: $SEGMENT"
echo "═══════════════════════════════════════════════════════════"

# Step 1: Generate per-segment domain CSVs locally
echo ""
echo "  [1/3] Generating domain CSVs..."
python3 - <<PYEOF
import csv, os

input_dir = "$INPUT_DIR"
today = "$TODAY"

# Split targets_apollo_peoplesearch.csv by segment
seg_map = {
    "IM_FIRST_AGENCIES": "IMAGENCY",
    "INFLUENCER_PLATFORMS": "INFPLAT",
    "SOCIAL_COMMERCE": "SOCCOM",
}
by_seg = {v: [] for v in seg_map.values()}

big = os.path.join(input_dir, "targets_apollo_peoplesearch.csv")
with open(big, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        seg_full = row.get("matched_segment", "").strip()
        if seg_full in seg_map:
            d = row.get("domain", "").strip()
            if d:
                by_seg[seg_map[seg_full]].append(d)

for seg_short, domains in by_seg.items():
    domains = list(dict.fromkeys(domains))  # dedup, preserve order
    out = os.path.join(input_dir, f"domains_{seg_short}_{today}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain"])
        for d in domains:
            w.writerow([d])
    print(f"    {seg_short}: {len(domains)} domains → {out}")

# AFFPERF from separate file
affperf_src = os.path.join(input_dir, "targets_AFFILIATE_PERFORMANCE_2026-04-10.csv")
affperf_domains = []
with open(affperf_src, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        d = row.get("domain", "").strip()
        if d:
            affperf_domains.append(d)
out = os.path.join(input_dir, f"domains_AFFPERF_{today}.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["domain"])
    for d in affperf_domains:
        w.writerow([d])
print(f"    AFFPERF: {len(affperf_domains)} domains → {out}")
PYEOF

# Step 2: SCP files to Hetzner
echo ""
echo "  [2/3] Uploading to Hetzner..."
scp "$SCRIPT_DIR/pipeline.py" "$HETZNER:$REMOTE_REPO/sofia/scripts/bace/pipeline.py"
scp "$INPUT_DIR/domains_IMAGENCY_${TODAY}.csv" "$HETZNER:$REMOTE_REPO/sofia/input/"
scp "$INPUT_DIR/domains_INFPLAT_${TODAY}.csv" "$HETZNER:$REMOTE_REPO/sofia/input/"
scp "$INPUT_DIR/domains_SOCCOM_${TODAY}.csv" "$HETZNER:$REMOTE_REPO/sofia/input/"
scp "$INPUT_DIR/domains_AFFPERF_${TODAY}.csv" "$HETZNER:$REMOTE_REPO/sofia/input/"
echo "  Done."

# Step 3: Run pipeline on Hetzner
echo ""
echo "  [3/3] Running Apollo search on Hetzner..."

run_segment() {
    local seg_short="$1"
    local seg_arg="$2"
    local domains_file="$REMOTE_REPO/sofia/input/domains_${seg_short}_${TODAY}.csv"

    echo ""
    echo "  ── $seg_short ──────────────────────────────────────"
    ssh "$HETZNER" "cd $REMOTE_REPO && set -a && source .env && set +a && python3 sofia/scripts/bace/pipeline.py people \
        --domains-csv $domains_file \
        --segment $seg_arg \
        --titles \"$TECHLEAD_TITLES\" \
        --seniorities \"$SENIORITIES\" \
        --max-people 5 \
        --search-only \
        --auto-approve"
}

case "$SEGMENT" in
    imagency) run_segment "IMAGENCY" "imagency" ;;
    infplat)  run_segment "INFPLAT"  "infplat" ;;
    soccom)   run_segment "SOCCOM"   "soccom" ;;
    affperf)  run_segment "AFFPERF"  "affperf" ;;
    all)
        run_segment "IMAGENCY" "imagency"
        run_segment "INFPLAT"  "infplat"
        run_segment "SOCCOM"   "soccom"
        run_segment "AFFPERF"  "affperf"
        ;;
    *)
        echo "ERROR: unknown segment '$SEGMENT'. Use: imagency|infplat|soccom|affperf|all"
        exit 1
        ;;
esac

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Done. Results on Hetzner: $REMOTE_REPO/sofia/output/OnSocial/pipeline/"
echo "═══════════════════════════════════════════════════════════"
