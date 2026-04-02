# Overseas Employee + Decision Maker Pipeline — Runbook

## What this does
1. Finds companies in a US state by industry + size (Clay TAM search)
2. Finds their overseas (non-US) employees to identify who hires abroad
3. Finds decision makers (HR, CEO, Finance) at those companies
4. Enriches emails via FindyMail API
5. Produces a 2-sheet XLSX: Companies (with overseas employee counts) + People (DMs with emails)

**Use case:** EasyStaff outreach — target US companies that hire overseas, contact their HR/Finance decision makers with personalized data about where they have employees.

---

## Prerequisites

### 1. Clay session cookie (expires every ~24h)
1. Go to `app.clay.com` → log in
2. DevTools (F12) → Application → Cookies → `api.clay.com` → copy `claysession` value
3. Check "Show URL-decoded" for the raw value
4. Set on Hetzner:
```bash
ssh hetzner "echo '{\"value\":\"PASTE_COOKIE_HERE\",\"savedAt\":\"2026-04-02T00:00:00.000Z\"}' > ~/magnum-opus-project/repo/scripts/clay/clay_session.json"
```

### 2. Pull latest code
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main"
```

---

## Step 1: TAM Company Search

Find companies in a specific state, filtered by "digital friendly" industries, 11-50 headcount.

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && node scripts/clay/clay_tam_export.js \
  --load-search 'All_remote_friendly' \
  --state STATE_NAME \
  --headless --auto"
```

**Replace `STATE_NAME`** with: Missouri, Texas, Florida, etc.

**What happens:**
- Loads 79 "All_remote_friendly" industry filters from Clay's saved search
- Applies size 11-50 and US country filter
- Adds state filter
- Exports companies to table
- Saves table ID to `exports/tam_results.json`

**Output:** Note the `tableId` from the output (e.g., `t_0tcrlkhqTwjuQXxTQhb`)

**Duration:** ~5-10 min (typing 79 industries)

**Cost:** 0 Clay credits

---

## Step 2: Find Overseas Employees

Run People search on the TAM table, excluding US-based people.

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && node scripts/clay/clay_people_search.js \
  --table-id TABLE_ID \
  --countries-exclude 'United States' \
  --headless --auto"
```

**Replace `TABLE_ID`** with the ID from Step 1.

**What happens:**
- Navigates to companies table → "+ Add" → "Find People" (Source)
- Applies "Countries to exclude: United States"
- Creates people table, reads results via API

**Output:** `exports/people_enrichment.json`

**Duration:** ~3-5 min

**Cost:** 0 Clay credits

---

## Step 3: Analyze Overseas Workers

Download data and run analysis locally to count non-US employees per company.

```bash
# Download
scp hetzner:~/magnum-opus-project/repo/scripts/clay/exports/people_enrichment.json /tmp/people_enrichment.json

# Run analysis (replace STATE_NAME)
python3 scripts/clay/analyze_overseas.py --state STATE_NAME
```

If `analyze_overseas.py` doesn't exist yet, use this inline command:

```bash
python3 << 'PYEOF'
import json, csv, re
from collections import defaultdict

# === EDIT THIS ===
STATE_NAME = "Missouri"
# =================

# Location-to-country mapping (abbreviated — full version in location_to_country.js)
LOC_MAP = {
    'greater st. louis': 'United States', 'kansas city metropolitan area': 'United States',
    'missouri area': 'United States', 'greater chicago area': 'United States',
    'new york city metropolitan area': 'United States', 'atlanta metropolitan area': 'United States',
    'san francisco bay area': 'United States', 'dallas-fort worth metroplex': 'United States',
    'los angeles metropolitan area': 'United States', 'denver metropolitan area': 'United States',
    'greater phoenix area': 'United States', 'greater boston': 'United States',
    'washington dc-baltimore area': 'United States', 'detroit metropolitan area': 'United States',
    'italia': 'Italy', 'brasil': 'Brazil', 'metro manila': 'Philippines',
    'greater melbourne area': 'Australia', 'greater sydney area': 'Australia',
    'greater delhi area': 'India', 'türkiye': 'Turkey', 'nederland': 'Netherlands',
    'schweiz': 'Switzerland', 'méxico': 'Mexico', 'czechia': 'Czech Republic',
    'دبي الإمارات العربية المتحدة': 'United Arab Emirates', 'الرياض السعودية': 'Saudi Arabia',
    'القاهرة مصر': 'Egypt',
}
US_STATES = ['alabama','alaska','arizona','arkansas','california','colorado','connecticut',
    'delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa','kansas',
    'kentucky','louisiana','maine','maryland','massachusetts','michigan','minnesota',
    'mississippi','missouri','montana','nebraska','nevada','new hampshire','new jersey',
    'new mexico','new york','north carolina','north dakota','ohio','oklahoma','oregon',
    'pennsylvania','rhode island','south carolina','south dakota','tennessee','texas',
    'utah','vermont','virginia','washington','west virginia','wisconsin','wyoming']

def to_country(loc):
    if not loc: return 'Unknown'
    n = loc.lower().strip()
    if n in LOC_MAP: return LOC_MAP[n]
    if n == 'united states': return 'United States'
    for k, v in LOC_MAP.items():
        if k in n: return v
    for s in US_STATES:
        if s in n: return 'United States'
    return loc.strip()

def normalize_domain(d):
    if not d: return ''
    d = d.lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')

with open('/tmp/people_enrichment.json') as f:
    people = json.load(f)

companies = defaultdict(lambda: {'name': '', 'domain': '', 'total': 0, 'us': 0, 'countries': defaultdict(int)})

for p in people:
    domain = normalize_domain(p.get('Company Domain', ''))
    if not domain: continue
    location = p.get('Location', '') or ''
    parts = [x.strip() for x in location.split(',')]
    raw_country = parts[-1] if len(parts) >= 2 else parts[0]
    country = to_country(raw_country)
    companies[domain]['domain'] = domain
    companies[domain]['name'] = p.get('Company Table Data') or companies[domain]['name']
    companies[domain]['total'] += 1
    if country == 'United States':
        companies[domain]['us'] += 1
    elif country != 'Unknown':
        companies[domain]['countries'][country] += 1

rows = []
for domain, data in companies.items():
    non_us = sum(data['countries'].values())
    if non_us == 0: continue
    sorted_c = sorted(data['countries'].items(), key=lambda x: -x[1])
    breakdown = ', '.join(f'{c}: {n}' for c, n in sorted_c)
    rows.append({
        'Company': data['name'], 'Domain': domain,
        'Total Employees': data['total'], 'US Employees': data['us'],
        'Non-US Employees': non_us, 'Non-US Breakdown': breakdown,
    })
rows.sort(key=lambda r: -r['Non-US Employees'])

csv_path = f'{STATE_NAME.lower()}_overseas_workers.csv'
with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['Company','Domain','Total Employees','US Employees','Non-US Employees','Non-US Breakdown'])
    writer.writeheader()
    writer.writerows(rows)

print(f'Companies with non-US employees: {len(rows)}')
print(f'CSV saved to: {csv_path}')
PYEOF
```

**Output:** `STATE_overseas_workers.csv` — companies with overseas employee counts

---

## Step 4: Find Decision Makers

Run People search on the SAME TAM table, with title filters, NO country exclusion.

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && \
  CLAY_CUSTOM_TITLES='[\"HR\",\"CEO\",\"COO\",\"Payroll\",\"Founder\",\"Accountant\",\"Finance\",\"CFO\",\"Head of HR\",\"Human Resources\",\"Controller\"]' \
  node scripts/clay/clay_people_search.js \
  --table-id TABLE_ID \
  --countries-exclude NONE \
  --headless --auto"
```

**Replace `TABLE_ID`** with the same ID from Step 1.

**What happens:**
- Same enrichment flow but WITH title filters and WITHOUT country exclusion
- Returns decision makers from ALL locations (mainly US-based)

**Output:** `exports/people_enrichment.json` (overwrites Step 2 output)

**IMPORTANT:** Download Step 2 results BEFORE running Step 4 (they share the same output file).

**Duration:** ~3-5 min

**Cost:** 0 Clay credits

---

## Step 5: Filter & Prepare DM List

Download the DM results and filter to only companies with overseas employees, max 4 per company.

```bash
# Download DM results
scp hetzner:~/magnum-opus-project/repo/scripts/clay/exports/people_enrichment.json /tmp/dm_people_all.json

# Filter (replace STATE_NAME and CSV path)
python3 << 'PYEOF'
import json, csv, re

def normalize_domain(d):
    if not d: return ''
    d = d.lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')

# Load companies with overseas employees
companies = set()
with open('STATE_overseas_workers.csv') as f:
    for row in csv.DictReader(f):
        companies.add(normalize_domain(row.get('Domain', '')))

# Filter people
with open('/tmp/dm_people_all.json') as f:
    all_people = json.load(f)

matched = []
counts = {}
for p in all_people:
    domain = normalize_domain(p.get('Company Domain', ''))
    if domain not in companies: continue
    counts[domain] = counts.get(domain, 0) + 1
    if counts[domain] <= 4:
        matched.append(p)

with open('/tmp/dm_717.json', 'w') as f:
    json.dump(matched, f, indent=2)
print(f'Filtered: {len(matched)} DMs at {len(set(counts.keys()))} companies')
PYEOF

# Upload filtered list to Hetzner for FindyMail
scp /tmp/dm_717.json hetzner:~/magnum-opus-project/repo/scripts/clay/exports/dm_people.json
```

---

## Step 6: FindyMail Email Enrichment

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && python3 scripts/clay/findymail_enrich_dm.py"
```

**What happens:**
- Reads `exports/dm_people.json`
- Calls FindyMail API for each person (LinkedIn URL first, name+domain fallback)
- 5 concurrent workers, resumes from cache if interrupted
- Saves to `exports/dm_people_with_emails.json`

**Duration:** ~2-5 min for ~700 people

**Cost:** ~1 FindyMail credit per person (~700 credits for 700 people)

---

## Step 7: Build Final XLSX

Download enriched data and build the 2-sheet report locally.

```bash
# Download
scp hetzner:~/magnum-opus-project/repo/scripts/clay/exports/dm_people_with_emails.json /tmp/dm_people_with_emails.json

# Build XLSX (replace paths)
python3 scripts/clay/build_overseas_xlsx.py \
  --companies STATE_overseas_workers.csv \
  --people /tmp/dm_people_with_emails.json \
  --output ~/Downloads/STATE_DM_Report.xlsx
```

**Output:** 2-sheet XLSX
- **Sheet 1 "Companies":** Company, Domain, Domain (core), DMs Found, Total/US/Non-US Employees, Breakdown
- **Sheet 2 "People":** # in Company, First Name, Last Name, Full Name, Email, Email Verified, Job Title, Company, Domain, Domain (core), Location, Country, LinkedIn, Overseas Employees, Breakdown, Top Countries

**Matching:** "Domain (core)" column on both sheets — use for VLOOKUP.

---

## Quick Reference — Run for a New State

Replace `STATE` everywhere:

```bash
# 1. Set fresh cookie (if expired)
ssh hetzner "echo '{\"value\":\"COOKIE\",\"savedAt\":\"...\"}' > ~/magnum-opus-project/repo/scripts/clay/clay_session.json"

# 2. TAM search
ssh hetzner "cd ~/magnum-opus-project/repo && node scripts/clay/clay_tam_export.js --load-search 'All_remote_friendly' --state STATE --headless --auto"
# Note the tableId from output

# 3. Overseas employees
ssh hetzner "cd ~/magnum-opus-project/repo && node scripts/clay/clay_people_search.js --table-id TABLE_ID --countries-exclude 'United States' --headless --auto"
scp hetzner:~/magnum-opus-project/repo/scripts/clay/exports/people_enrichment.json /tmp/people_enrichment.json
# Run analysis → state_overseas_workers.csv

# 4. Decision makers
ssh hetzner "cd ~/magnum-opus-project/repo && CLAY_CUSTOM_TITLES='[\"HR\",\"CEO\",\"COO\",\"Payroll\",\"Founder\",\"Accountant\",\"Finance\",\"CFO\",\"Head of HR\",\"Human Resources\",\"Controller\"]' node scripts/clay/clay_people_search.js --table-id TABLE_ID --countries-exclude NONE --headless --auto"
scp hetzner:~/magnum-opus-project/repo/scripts/clay/exports/people_enrichment.json /tmp/dm_people_all.json
# Filter → upload dm_people.json

# 5. FindyMail
ssh hetzner "cd ~/magnum-opus-project/repo && python3 scripts/clay/findymail_enrich_dm.py"

# 6. Build report
scp hetzner:~/magnum-opus-project/repo/scripts/clay/exports/dm_people_with_emails.json /tmp/dm_people_with_emails.json
python3 scripts/clay/build_overseas_xlsx.py --companies state_overseas_workers.csv --people /tmp/dm_people_with_emails.json --output ~/Downloads/STATE_DM_Report.xlsx
```

---

## Cost Summary

| Step | Cost |
|------|------|
| TAM company search | 0 (free Puppeteer) |
| Overseas employee search | 0 (free Puppeteer) |
| Decision maker search | 0 (free Puppeteer) |
| FindyMail enrichment | ~1 credit/person (~$0.01/person) |
| **Total for ~700 DMs** | **~700 FindyMail credits** |

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/clay/clay_session.json` | Clay session cookie |
| `scripts/clay/clay_tam_export.js` | Company search (Step 1) |
| `scripts/clay/clay_people_search.js` | People search (Steps 2 & 4) |
| `scripts/clay/findymail_enrich_dm.py` | Email enrichment (Step 5) |
| `scripts/clay/location_to_country.js` | Location → country mapping |
| `scripts/clay/build_overseas_xlsx.py` | XLSX report builder (Step 7) |
| `scripts/clay/exports/` | All output files |
| `scripts/clay/OVERSEAS_DM_RUNBOOK.md` | This file |

---

## Troubleshooting

**Clay session expired:**
Log into Clay browser → DevTools → Cookies → copy claysession → set on Hetzner

**Script can't find buttons/inputs:**
Check screenshots in `exports/` — Clay may have updated their UI

**FindyMail stuck:**
Script has persistent cache at `/tmp/findymail_dm_cache.json`. Just rerun — it resumes from cache.

**"Table of companies" not working in People search:**
The enrichment flow (+ Add → Find People) bypasses this. Use `--table-id` flag.

**Industries typed one by one (slow):**
Use `--load-search 'All_remote_friendly'` to load from Clay's saved search. If that fails, industries are typed manually (~5 min for 79).
