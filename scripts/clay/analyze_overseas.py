#!/usr/bin/env python3
"""
Step 3 of the Overseas DM Pipeline: Analyze overseas workers.

Reads people_enrichment.json (non-US employees from Clay),
groups by company, counts employees per country,
outputs CSV with exact columns expected by build_overseas_xlsx.py.

Usage:
  python3 analyze_overseas.py --input /tmp/people_enrichment.json --state Missouri
  python3 analyze_overseas.py --input /tmp/people_enrichment.json --state Ohio --output ~/Downloads/

Output CSV columns (MUST match exactly — build_overseas_xlsx.py depends on this):
  Company, Domain, Total Employees, US Employees, Non-US Employees, Non-US Breakdown

Non-US Breakdown format: "India: 12, Philippines: 5, United Kingdom: 3"
"""

import argparse
import csv
import json
import re
import os
from collections import defaultdict

# ============================================================
# Location-to-Country mapping
# Normalizes Clay's raw locations (metro areas, Arabic text, etc.)
# to standard country names.
# ============================================================

LOC_MAP = {
    # US metro areas / regions
    'greater st. louis': 'United States', 'kansas city metropolitan area': 'United States',
    'missouri area': 'United States', 'greater chicago area': 'United States',
    'new york city metropolitan area': 'United States', 'new york metropolitan area': 'United States',
    'atlanta metropolitan area': 'United States', 'san francisco bay area': 'United States',
    'greater minneapolis-st. paul area': 'United States', 'dallas-fort worth metroplex': 'United States',
    'los angeles metropolitan area': 'United States', 'denver metropolitan area': 'United States',
    'greater tampa bay area': 'United States', 'greater phoenix area': 'United States',
    'greater houston': 'United States', 'detroit metropolitan area': 'United States',
    'greater boston': 'United States', 'washington dc-baltimore area': 'United States',
    'south carolina area': 'United States', 'texas metropolitan area': 'United States',
    'oregon metropolitan area': 'United States', 'greater indianapolis': 'United States',
    'greater cleveland': 'United States', 'greater philadelphia': 'United States',
    'miami-fort lauderdale area': 'United States', 'greater lexington area': 'United States',
    'oklahoma city metropolitan area': 'United States', 'iowa city-cedar rapids area': 'United States',
    'little rock metropolitan area': 'United States', 'joplin metropolitan area': 'United States',
    'greater milwaukee': 'United States', 'omaha metropolitan area': 'United States',
    'des moines metropolitan area': 'United States', 'ohio metropolitan area': 'United States',
    'boise metropolitan area': 'United States', 'greater colorado springs area': 'United States',
    'peoria metropolitan area': 'United States', 'greater tucson area': 'United States',
    'pensacola metropolitan area': 'United States', 'grand rapids metropolitan area': 'United States',
    'kansas metropolitan area': 'United States', 'greater chattanooga': 'United States',
    'greater wilmington area': 'United States', 'greater eugene-springfield area': 'United States',
    'greater lansing': 'United States', 'greater kennewick area': 'United States',
    'greater richmond region': 'United States', 'greater reno area': 'United States',
    'greater evansville area': 'United States', 'greater jackson area': 'United States',
    'greater hartford': 'United States', 'greater orlando': 'United States',
    'memphis metropolitan area': 'United States', 'urbana-champaign area': 'United States',
    'greater columbus area': 'United States', 'greater reading area': 'United States',
    'greater cincinnati': 'United States', 'greater pittsburgh': 'United States',
    'nashville metropolitan area': 'United States', 'charlotte metropolitan area': 'United States',
    'columbus ohio metropolitan area': 'United States', 'cincinnati metropolitan area': 'United States',
    'cleveland metropolitan area': 'United States', 'dayton metropolitan area': 'United States',
    'akron metropolitan area': 'United States', 'toledo metropolitan area': 'United States',
    'youngstown metropolitan area': 'United States',
    # Canada
    'greater montreal metropolitan area': 'Canada', 'greater ottawa metropolitan area': 'Canada',
    'greater toronto area': 'Canada', 'greater vancouver metropolitan area': 'Canada',
    # Italy
    'italia': 'Italy', 'greater modena metropolitan area': 'Italy', 'italy metropolitan area': 'Italy',
    # Brazil
    'brasil': 'Brazil', 'são paulo e região': 'Brazil',
    # Colombia
    'bogotá d.c. metropolitan area': 'Colombia',
    # Philippines
    'metro manila': 'Philippines',
    # Australia
    'greater melbourne area': 'Australia', 'greater sydney area': 'Australia',
    'greater brisbane area': 'Australia', 'greater perth area': 'Australia',
    # India
    'greater delhi area': 'India', 'greater hyderabad area': 'India', 'mumbai metropolitan region': 'India',
    # UK
    'greater cambridge area': 'United Kingdom', 'greater derby area': 'United Kingdom',
    'greater sheffield area': 'United Kingdom', 'greater leicester area': 'United Kingdom',
    # France
    'greater paris metropolitan region': 'France',
    # Germany
    'frankfurt/rhein-main': 'Germany',
    # Switzerland
    'schweiz': 'Switzerland', 'greater zurich area': 'Switzerland',
    # Sweden
    'sverige': 'Sweden',
    # Spain
    'madrid y alrededores': 'Spain',
    # Belgium
    'brussels metropolitan area': 'Belgium',
    # Japan
    '日本 東京都': 'Japan',
    # Mexico
    'méxico': 'Mexico', 'área metropolitana de ciudad de méxico': 'Mexico', 'mexico city metropolitan area': 'Mexico',
    # Arabic locations
    'دبي الإمارات العربية المتحدة': 'United Arab Emirates',
    'الإمارات العربية المتحدة': 'United Arab Emirates',
    'الرياض السعودية': 'Saudi Arabia',
    'القاهرة مصر': 'Egypt', 'الاسكندرية مصر': 'Egypt',
    'الدار البيضاء سطات المغرب': 'Morocco',
    'ولاية تونس تونس': 'Tunisia',
    # Turkey
    'türkiye': 'Turkey',
    # Netherlands
    'nederland': 'Netherlands',
    # Ukraine
    'kyiv metropolitan area': 'Ukraine',
    # Czechia
    'czechia': 'Czech Republic',
}

US_STATES = [
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york', 'north carolina',
    'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania',
    'rhode island', 'south carolina', 'south dakota', 'tennessee', 'texas',
    'utah', 'vermont', 'virginia', 'washington', 'west virginia',
    'wisconsin', 'wyoming', 'district of columbia',
]


def to_country(location):
    if not location:
        return 'Unknown'
    norm = location.lower().strip()
    if norm in LOC_MAP:
        return LOC_MAP[norm]
    if norm == 'united states':
        return 'United States'
    for key, country in LOC_MAP.items():
        if key in norm:
            return country
    for state in US_STATES:
        if state in norm:
            return 'United States'
    return location.strip()


def normalize_domain(d):
    if not d:
        return ''
    d = d.lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')


def main():
    parser = argparse.ArgumentParser(description='Analyze overseas workers from Clay people data')
    parser.add_argument('--input', required=True, help='Path to people_enrichment.json')
    parser.add_argument('--state', required=True, help='State name (e.g., Missouri, Ohio, Texas)')
    parser.add_argument('--output', default='.', help='Output directory (default: current dir)')
    args = parser.parse_args()

    with open(args.input) as f:
        people = json.load(f)

    print(f'Total people loaded: {len(people)}')

    # Group by company domain
    companies = defaultdict(lambda: {'name': '', 'domain': '', 'total': 0, 'us': 0, 'countries': defaultdict(int)})

    for p in people:
        domain = normalize_domain(p.get('Company Domain', ''))
        if not domain:
            continue
        location = p.get('Location', '') or ''
        parts = [x.strip() for x in location.split(',')]
        raw_country = parts[-1] if len(parts) >= 2 else parts[0]
        country = to_country(raw_country)

        companies[domain]['domain'] = domain
        companies[domain]['name'] = p.get('Company Table Data') or p.get('Company Name') or companies[domain]['name']
        companies[domain]['total'] += 1
        if country == 'United States':
            companies[domain]['us'] += 1
        elif country != 'Unknown':
            companies[domain]['countries'][country] += 1

    # Build rows — only companies with non-US employees
    rows = []
    for domain, data in companies.items():
        non_us = sum(data['countries'].values())
        if non_us == 0:
            continue
        sorted_countries = sorted(data['countries'].items(), key=lambda x: -x[1])
        breakdown = ', '.join(f'{c}: {n}' for c, n in sorted_countries)
        rows.append({
            'Company': data['name'],
            'Domain': domain,
            'Total Employees': data['total'],
            'US Employees': data['us'],
            'Non-US Employees': non_us,
            'Non-US Breakdown': breakdown,
        })

    rows.sort(key=lambda r: -r['Non-US Employees'])

    # Output CSV
    state_lower = args.state.lower().replace(' ', '_')
    csv_filename = f'{state_lower}_overseas_workers.csv'
    csv_path = os.path.join(args.output, csv_filename)

    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Company', 'Domain', 'Total Employees', 'US Employees',
            'Non-US Employees', 'Non-US Breakdown',
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f'\nResults:')
    print(f'  Companies with non-US employees: {len(rows)}')
    print(f'  Total non-US people: {sum(r["Non-US Employees"] for r in rows)}')
    print(f'  CSV saved to: {csv_path}')

    # Show top 10
    print(f'\nTop 10 companies:')
    for r in rows[:10]:
        print(f'  {r["Company"]:35s} {r["Domain"]:25s} Non-US:{r["Non-US Employees"]:>3d}  {r["Non-US Breakdown"][:50]}')


if __name__ == '__main__':
    main()
