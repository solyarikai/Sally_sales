#!/usr/bin/env python3
import json, os
d = "/scripts/data/raw_contacts"
files = sorted(os.listdir(d))
print(f"Raw files: {len(files)}")
for f in files[:3]:
    data = json.load(open(os.path.join(d, f)))
    has = sum(1 for c in data if c.get("schools"))
    print(f"{f[:60]}: {len(data)} contacts, {has} with schools")
    if has:
        for c in data:
            if c.get("schools"):
                print(f"  EXAMPLE: {c['name']} | schools={c['schools']}")
                break
