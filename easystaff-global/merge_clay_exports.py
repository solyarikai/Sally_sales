#!/usr/bin/env python3
"""Merge all Clay CSV exports from data/clay_exports/ into a single deduplicated dataset.

Reads au_ph_*.csv files, normalizes LinkedIn URLs, deduplicates, and tracks
origin signals (language/university) extracted from filenames.

Usage: python3 easystaff-global/merge_clay_exports.py
"""
import csv
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLAY_EXPORTS_DIR = os.path.join(BASE_DIR, 'data', 'clay_exports')
DATA_DIR = os.path.join(BASE_DIR, 'data')
SEARCH_LOG_PATH = os.path.join(DATA_DIR, 'au_ph_search_log.json')

# Language keywords to detect in filenames
LANGUAGE_KEYWORDS = ['tagalog', 'filipino', 'cebuano', 'ilocano', 'bisaya']

# Column name variants Clay exports may use
COLUMN_VARIANTS = {
    'first_name': ['First Name', 'first_name', 'firstName', 'First name'],
    'last_name': ['Last Name', 'last_name', 'lastName', 'Last name'],
    'full_name': ['Name', 'Full Name', 'name', 'full_name', 'fullName', 'Full name'],
    'company': ['Company Name', 'Company', 'company', 'company_name', 'companyName', 'Organization Name'],
    'title': ['Job Title', 'Title', 'title', 'job_title', 'jobTitle', 'Position'],
    'location': ['Location', 'location', 'Person Location', 'City'],
    'linkedin_url': ['LinkedIn URL', 'LinkedIn', 'linkedin_url', 'linkedinUrl',
                     'LinkedIn Url', 'Person Linkedin Url', 'LinkedIn Profile URL',
                     'linkedin', 'Profile URL'],
    'domain': ['Domain', 'domain', 'Company Domain', 'Website'],
    'schools': ['Schools', 'schools', 'Education', 'School', 'University'],
    'languages': ['Languages', 'languages', 'Language'],
}


def normalize_linkedin_url(url):
    """Lowercase, strip trailing /, strip query params."""
    if not url or not isinstance(url, str):
        return ''
    url = url.strip().lower()
    # Strip query params
    parsed = urlparse(url)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme else url.split('?')[0]
    # Strip trailing slash
    clean = clean.rstrip('/')
    return clean


def resolve_column(headers, field_name):
    """Find the actual column name from headers, trying known variants."""
    variants = COLUMN_VARIANTS.get(field_name, [])
    for v in variants:
        if v in headers:
            return v
    return None


def extract_signals_from_filename(filename):
    """Extract origin signals from a Clay export filename.

    Examples:
        au_ph_tagalog_sydney.csv -> ['language:tagalog']
        au_ph_uni_ateneo_de_manila.csv -> ['university:ateneo de manila']
        au_ph_cebuano_melbourne.csv -> ['language:cebuano']
    """
    signals = []
    base = os.path.splitext(filename)[0].lower()

    # Check for language keywords
    for lang in LANGUAGE_KEYWORDS:
        if lang in base:
            signals.append(f'language:{lang}')

    # Check for university prefix: uni_{name}_...
    uni_match = re.search(r'uni_([a-z0-9_]+?)(?:_(?:sydney|melbourne|brisbane|perth|adelaide|gold_coast|australia))?$', base)
    if uni_match:
        uni_name = uni_match.group(1).replace('_', ' ').strip()
        if uni_name:
            signals.append(f'university:{uni_name}')

    return signals


def read_csv_file(filepath):
    """Read a single Clay CSV export, handling BOM and column variants."""
    contacts = []
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print(f"  WARN: {filename} has no headers, skipping")
            return []

        headers = list(reader.fieldnames)

        # Resolve column mappings
        col_first = resolve_column(headers, 'first_name')
        col_last = resolve_column(headers, 'last_name')
        col_full = resolve_column(headers, 'full_name')
        col_company = resolve_column(headers, 'company')
        col_title = resolve_column(headers, 'title')
        col_location = resolve_column(headers, 'location')
        col_linkedin = resolve_column(headers, 'linkedin_url')
        col_domain = resolve_column(headers, 'domain')
        col_schools = resolve_column(headers, 'schools')
        col_languages = resolve_column(headers, 'languages')

        for row in reader:
            # Extract name
            first_name = (row.get(col_first, '') or '').strip() if col_first else ''
            last_name = (row.get(col_last, '') or '').strip() if col_last else ''
            full_name = (row.get(col_full, '') or '').strip() if col_full else ''

            if not first_name and not last_name and full_name:
                parts = full_name.split(None, 1)
                first_name = parts[0] if parts else ''
                last_name = parts[1] if len(parts) > 1 else ''

            if not full_name and (first_name or last_name):
                full_name = f"{first_name} {last_name}".strip()

            company = (row.get(col_company, '') or '').strip() if col_company else ''
            title = (row.get(col_title, '') or '').strip() if col_title else ''
            location = (row.get(col_location, '') or '').strip() if col_location else ''
            linkedin_url = (row.get(col_linkedin, '') or '').strip() if col_linkedin else ''
            domain = (row.get(col_domain, '') or '').strip() if col_domain else ''
            schools = (row.get(col_schools, '') or '').strip() if col_schools else ''
            languages = (row.get(col_languages, '') or '').strip() if col_languages else ''

            linkedin_url = normalize_linkedin_url(linkedin_url)

            # Skip rows with no identifying info
            if not linkedin_url and not full_name:
                continue

            contacts.append({
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'company': company,
                'title': title,
                'location': location,
                'linkedin_url': linkedin_url,
                'domain': domain,
                'schools': schools,
                'languages': languages,
                'source_file': filename,
            })

    return contacts


def build_dedup_key(contact):
    """Build dedup key: LinkedIn URL if available, else first+last+company."""
    if contact['linkedin_url']:
        return ('linkedin', contact['linkedin_url'])
    else:
        name_key = f"{contact['first_name'].lower()}|{contact['last_name'].lower()}|{contact['company'].lower()}"
        return ('name_company', name_key)


def merge_contact(existing, new_contact, new_signals, new_source):
    """Merge a duplicate contact — combine signals and search_ids, keep richest data."""
    # Add new signals
    for sig in new_signals:
        if sig not in existing['origin_signals']:
            existing['origin_signals'].append(sig)

    # Add source file
    if new_source not in existing['search_ids']:
        existing['search_ids'].append(new_source)

    # Fill in empty fields from new contact
    for field in ['company', 'title', 'location', 'domain', 'schools', 'languages', 'linkedin_url']:
        if not existing.get(field) and new_contact.get(field):
            existing[field] = new_contact[field]


def load_search_log():
    """Load au_ph_search_log.json if it exists."""
    if not os.path.exists(SEARCH_LOG_PATH):
        return {}
    with open(SEARCH_LOG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def enrich_from_search_log(merged, search_log):
    """Enrich origin signals using search log metadata."""
    if not search_log:
        return

    # Build filename -> search log entry mapping
    file_signals = {}
    entries = search_log if isinstance(search_log, list) else search_log.get('searches', search_log.get('entries', []))
    if isinstance(entries, dict):
        # Handle {filename: {metadata}} format
        for fname, meta in entries.items():
            signals = []
            if isinstance(meta, dict):
                if meta.get('language'):
                    signals.append(f"language:{meta['language'].lower()}")
                if meta.get('university'):
                    signals.append(f"university:{meta['university'].lower()}")
                if meta.get('signal'):
                    signals.append(meta['signal'])
                if meta.get('signals'):
                    signals.extend(meta['signals'] if isinstance(meta['signals'], list) else [meta['signals']])
            file_signals[fname] = signals
    elif isinstance(entries, list):
        for entry in entries:
            fname = entry.get('filename', entry.get('file', ''))
            signals = []
            if entry.get('language'):
                signals.append(f"language:{entry['language'].lower()}")
            if entry.get('university'):
                signals.append(f"university:{entry['university'].lower()}")
            if entry.get('signal'):
                signals.append(entry['signal'])
            if entry.get('signals'):
                signals.extend(entry['signals'] if isinstance(entry['signals'], list) else [entry['signals']])
            if fname:
                file_signals[fname] = signals

    if not file_signals:
        return

    enriched_count = 0
    for contact in merged.values():
        for source in contact['search_ids']:
            extra_signals = file_signals.get(source, [])
            for sig in extra_signals:
                if sig and sig not in contact['origin_signals']:
                    contact['origin_signals'].append(sig)
                    enriched_count += 1

    if enriched_count:
        print(f"  Enriched {enriched_count} signals from search log")


def main():
    # Find all matching CSVs
    pattern = os.path.join(CLAY_EXPORTS_DIR, 'au_ph_*.csv')
    csv_files = sorted(glob.glob(pattern))

    if not csv_files:
        print(f"No CSV files matching 'au_ph_*.csv' found in {CLAY_EXPORTS_DIR}")
        print("Make sure Clay exports are placed in easystaff-global/data/clay_exports/")
        sys.exit(1)

    print(f"Found {len(csv_files)} CSV files to merge\n")

    # Read all contacts
    all_contacts = []
    file_stats = {}
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        contacts = read_csv_file(filepath)
        file_stats[filename] = len(contacts)
        all_contacts.extend(contacts)
        signals = extract_signals_from_filename(filename)
        sig_str = f" [{', '.join(signals)}]" if signals else ''
        print(f"  {filename}: {len(contacts)} contacts{sig_str}")

    print(f"\nTotal contacts (raw): {len(all_contacts)}")

    # Deduplicate
    merged = {}  # dedup_key -> contact dict
    for contact in all_contacts:
        key = build_dedup_key(contact)
        source_file = contact['source_file']
        signals = extract_signals_from_filename(source_file)

        if key in merged:
            merge_contact(merged[key], contact, signals, source_file)
        else:
            merged[key] = {
                'first_name': contact['first_name'],
                'last_name': contact['last_name'],
                'full_name': contact['full_name'],
                'company': contact['company'],
                'title': contact['title'],
                'location': contact['location'],
                'linkedin_url': contact['linkedin_url'],
                'domain': contact['domain'],
                'schools': contact['schools'],
                'languages': contact['languages'],
                'origin_signals': list(signals),
                'search_ids': [source_file],
            }

    # Enrich from search log
    search_log = load_search_log()
    if search_log:
        print("\nEnriching from search log...")
        enrich_from_search_log(merged, search_log)

    unique_contacts = list(merged.values())
    dupes_removed = len(all_contacts) - len(unique_contacts)

    # Signal distribution
    signal_counter = Counter()
    multi_signal = 0
    no_signal = 0
    for c in unique_contacts:
        for sig in c['origin_signals']:
            signal_counter[sig] += 1
        if len(c['origin_signals']) > 1:
            multi_signal += 1
        if not c['origin_signals']:
            no_signal += 1

    # Output
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(DATA_DIR, f'au_ph_merged_{timestamp}.json')

    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'total_csvs': len(csv_files),
            'total_raw': len(all_contacts),
            'total_unique': len(unique_contacts),
            'duplicates_removed': dupes_removed,
            'signal_distribution': dict(signal_counter.most_common()),
            'source_files': file_stats,
        },
        'contacts': unique_contacts,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print(f"MERGE SUMMARY")
    print(f"{'='*60}")
    print(f"CSVs loaded:        {len(csv_files)}")
    print(f"Total contacts:     {len(all_contacts)}")
    print(f"Unique after dedup: {len(unique_contacts)}")
    print(f"Duplicates removed: {dupes_removed}")
    print(f"Multi-signal:       {multi_signal} contacts found in 2+ searches")
    print(f"No signal:          {no_signal} contacts (filename had no language/uni tag)")
    print()

    if signal_counter:
        print("Signal distribution:")
        for sig, count in signal_counter.most_common():
            print(f"  {sig}: {count}")
        print()

    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
