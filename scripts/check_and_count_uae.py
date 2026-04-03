#!/usr/bin/env python3
import json

data = json.load(open('/tmp/uae_pk_enriched_all.json'))
uae_kw = ['dubai', 'abu dhabi', 'uae', 'united arab', 'sharjah', 'ajman',
           '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a', '\u062f\u0628\u064a',
           '\u0623\u0628\u0648 \u0638\u0628\u064a']

with_email = [c for c in data if c.get('email')]
uae_with_email = [c for c in with_email
                  if any(k in (c.get('location') or '').lower() for k in uae_kw)]
non_uae_with_email = [c for c in with_email
                      if not any(k in (c.get('location') or '').lower() for k in uae_kw)]

print(f"Total with email: {len(with_email)}")
print(f"UAE with email: {len(uae_with_email)}")
print(f"Non-UAE with email (shouldn't be in campaign): {len(non_uae_with_email)}")

# Show non-UAE emails that got added
for c in non_uae_with_email[:5]:
    print(f"  {c.get('email'):35s} {c.get('location', '')[:40]}")
