#!/bin/bash
# Crowd Project — Find people at AI companies
# Run on Hetzner: ./run_crowd_search.sh

cd /app/scripts/clay

echo "=== Crowd: AI Companies People Search ==="
echo "Companies: 167"
echo "Titles: CEO, Founder, CMO, Head of Marketing, VP Marketing, Head of Growth, etc."
echo ""

node clay_enrich.js \
  --file crowd_ai_companies.csv \
  --find-people \
  --titles "CEO,Founder,Co-Founder,CMO,Head of Marketing,VP of Marketing,Head of Growth,Director of Marketing,Head of Influencer Marketing,Head of Creator Partnerships,Influencer Marketing Manager,Growth Marketing Manager,Marketing Manager" \
  --headless \
  --auto \
  --output exports/crowd_people.json

echo ""
echo "=== Done! Results in exports/crowd_people.json ==="
