#!/usr/bin/env python3
"""
Consolidate all Clay People Search exports into corridor-specific files.

Clay overwrites people_batch_*.json on each run. This script:
1. Reads ALL Clay exports (current + backed up)
2. Deduplicates by LinkedIn URL
3. Saves to /scripts/data/{corridor}_clay_all.json (append-only)

Run after each Clay search to preserve results.

Usage:
  python3 scripts/consolidate_clay.py uae-pakistan
  python3 scripts/consolidate_clay.py au-philippines
  python3 scripts/consolidate_clay.py arabic-southafrica
  python3 scripts/consolidate_clay.py all
"""
import json
import os
import sys
import glob

DATA_DIR = '/scripts/data' if os.path.isdir('/scripts/data') else os.path.expanduser('~/magnum-opus-project/repo/scripts/data')
CLAY_DIR = '/scripts/clay/exports' if os.path.isdir('/scripts/clay/exports') else os.path.expanduser('~/magnum-opus-project/repo/scripts/clay/exports')


def consolidate(corridor_slug):
    out_file = os.path.join(DATA_DIR, f'{corridor_slug}_clay_all.json')

    # Load existing consolidated data
    existing = []
    if os.path.exists(out_file):
        existing = json.load(open(out_file))

    # Load ALL Clay exports (current)
    new_records = []
    for pattern in ['people_all.json', 'people_batch_*.json', 'people_filter_based.json']:
        for f in glob.glob(os.path.join(CLAY_DIR, pattern)):
            try:
                data = json.load(open(f))
                if isinstance(data, list):
                    new_records.extend(data)
            except Exception:
                pass

    # Load backups
    for backup_dir in glob.glob(os.path.join(DATA_DIR, 'clay_backup_*')):
        for pattern in ['people_all.json', 'people_batch_*.json', 'people_filter_based.json']:
            for f in glob.glob(os.path.join(backup_dir, pattern)):
                try:
                    data = json.load(open(f))
                    if isinstance(data, list):
                        new_records.extend(data)
                except Exception:
                    pass

    # Merge existing + new
    all_records = existing + new_records

    # Deduplicate by LinkedIn URL (primary) or name+company (fallback)
    seen = set()
    deduped = []
    for r in all_records:
        li = (r.get('LinkedIn Profile') or r.get('linkedin_profile') or '').lower().strip().rstrip('/')
        name = (r.get('Full Name') or r.get('full_name') or f"{r.get('First Name', '')} {r.get('Last Name', '')}").strip().lower()
        company = (r.get('Company Name') or r.get('company_name') or r.get('Company Domain') or '').lower().strip()

        key = li if li else f"{name}|{company}"
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    # Save
    with open(out_file, 'w') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print(f'{corridor_slug}: {len(existing)} existing + {len(new_records)} new → {len(deduped)} unique (from {len(all_records)} total)')
    print(f'Saved to: {out_file}')
    return len(deduped)


def main():
    corridors = sys.argv[1:] if len(sys.argv) > 1 else ['all']
    if 'all' in corridors:
        corridors = ['uae_pakistan', 'au_philippines', 'arabic_southafrica']

    for corridor in corridors:
        slug = corridor.replace('-', '_')
        consolidate(slug)


if __name__ == '__main__':
    main()
