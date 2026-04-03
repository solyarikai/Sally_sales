#!/usr/bin/env python3
"""Prep domain batch files for Clay/Apollo browser enrichment."""
import json

domains = json.load(open("/tmp/uae_pk_need_browser_enrich.json"))
print(f"Total companies: {len(domains)}")

# Split into batches of 200 for Clay
batch_size = 200
batches = [domains[i:i+batch_size] for i in range(0, len(domains), batch_size)]
print(f"Batches: {len(batches)}")

for i, b in enumerate(batches):
    path = f"/tmp/uae_pk_enrich_batch_{i+1}.txt"
    with open(path, "w") as f:
        f.write("\n".join(d["domain"] for d in b))
    print(f"  Batch {i+1}: {len(b)} domains -> {path}")

# All domains for Apollo
all_doms = [d["domain"] for d in domains]
with open("/tmp/uae_pk_all_enrich_domains.txt", "w") as f:
    f.write("\n".join(all_doms))
print(f"All domains: /tmp/uae_pk_all_enrich_domains.txt ({len(all_doms)})")
