#!/usr/bin/env python3
import json
from collections import Counter

data = json.load(open('/tmp/uae_pk_enriched_all.json'))
uae_kw = ['dubai', 'abu dhabi', 'uae', 'united arab', 'sharjah', 'ajman']
uae = 0
non_uae = []
for c in data:
    loc = (c.get('location') or '').lower()
    if any(k in loc for k in uae_kw):
        uae += 1
    else:
        non_uae.append(loc or '(empty)')

print(f'UAE-located: {uae}/{len(data)}')
if non_uae:
    print(f'Non-UAE ({len(non_uae)}):')
    for loc, cnt in Counter(non_uae).most_common(10):
        print(f'  {cnt}x  {loc}')
