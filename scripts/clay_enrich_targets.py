#!/usr/bin/env python3
"""
Generate domain list for Clay enrichment of TARGET companies.

After scoring, we have ~620 target companies with ~1.1 contacts each.
Clay People Search (FREE, 0 credits) can find up to 3 decision-makers
per company by searching: company domain + country filter.

This script:
1. Reads scored output
2. Counts contacts per company
3. Exports domains that need more contacts (< 3) to CSV
4. The CSV is used with clay_people_search.js

Usage (inside Docker):
  python3 /scripts/clay_enrich_targets.py uae-pakistan
  python3 /scripts/clay_enrich_targets.py au-philippines

Output: /scripts/data/{corridor}_clay_enrich_domains.csv
Then run: node scripts/clay/clay_people_search.js --domains-file {csv} --countries "Pakistan" --headless --auto
"""
import json
import os
import sys

if os.path.isdir('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

DATA_DIR = '/scripts/data' if os.path.isdir('/scripts/data') else '/tmp'

CORRIDOR_COUNTRY = {
    'uae-pakistan': 'Pakistan',
    'au-philippines': 'Philippines',
    'arabic-southafrica': 'South Africa',
}

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 clay_enrich_targets.py <corridor>")
        return

    corridor = sys.argv[1]
    slug = corridor.replace('-', '_')
    country = CORRIDOR_COUNTRY.get(corridor, 'Pakistan')

    scored_file = f'{DATA_DIR}/{slug}_v8_scored.json'
    if not os.path.exists(scored_file):
        print(f"No scored file: {scored_file}")
        return

    scored = json.load(open(scored_file))
    print(f"Scored contacts: {len(scored)}")

    # Count contacts per domain
    from collections import Counter
    domain_counts = Counter(s['domain'] for s in scored if s['domain'])
    total_companies = len(domain_counts)

    need_more = {d: 3 - c for d, c in domain_counts.items() if c < 3}
    full = sum(1 for c in domain_counts.values() if c >= 3)
    total_slots = sum(need_more.values())

    print(f"Companies: {total_companies}")
    print(f"  Already 3 contacts: {full}")
    print(f"  Need more contacts: {len(need_more)}")
    print(f"  Total slots to fill: {total_slots}")

    # Write domains to CSV
    out_file = f'{DATA_DIR}/{slug}_clay_enrich_domains.csv'
    with open(out_file, 'w') as f:
        for d in sorted(need_more.keys()):
            f.write(d + '\n')

    print(f"\nWrote {len(need_more)} domains to {out_file}")
    print(f"Batches needed: {(len(need_more) + 199) // 200} (200 domains/batch)")
    print(f"Estimated time: ~{(len(need_more) + 199) // 200 * 3} min")
    # APPROACH: Don't filter by talent-country origin. The COMPANY is already validated.
    # Now find ANY decision-maker at this company in the buyer country.
    # EasyStaff decision-makers: CFO, COO, HR Director, CEO, Founder, VP Finance/Ops
    buyer_country = {
        'uae-pakistan': 'United Arab Emirates',
        'au-philippines': 'Australia',
        'arabic-southafrica': 'Qatar,Saudi Arabia,Bahrain,Kuwait,Oman,United Arab Emirates',
    }.get(corridor, 'United Arab Emirates')

    print(f"\nTo run Clay enrichment (decision-makers at target companies):")
    print(f"  node scripts/clay/clay_people_search.js \\")
    print(f"    --domains-file {out_file} \\")
    print(f"    --countries \"{buyer_country}\" \\")
    print(f"    --titles \\")
    print(f"    --headless --auto")
    print(f"\n  This finds CFO/COO/HR/CEO/Founder at target companies in {buyer_country}.")
    print(f"  NOT filtered by Pakistan origin — company already validated as ICP.")
    print(f"  Result: up to 3 decision-makers per company → ~{total_slots} new contacts.")


if __name__ == '__main__':
    main()
