#!/usr/bin/env python3
"""Find the Susanne Koning row and check clean CSV output."""
import csv, glob, os

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'getsales_exports')
TARGET_UUID = '47591caa-f525-47e9-965f-90c79c55f158'

# Find in raw CSVs
files = sorted(glob.glob(os.path.join(EXPORT_DIR, 'contacts_export_*.csv')))
for f in files:
    with open(f, 'r', encoding='utf-8', errors='replace') as fh:
        reader = csv.reader(fh)
        header = next(reader)
        for row in reader:
            if row[0] == TARGET_UUID:
                print("Found in: {}".format(os.path.basename(f)))
                print("Cols: {}".format(len(row)))
                for i, cell in enumerate(row):
                    val = repr(cell[:120])
                    if len(cell) > 120:
                        val += "...({} chars)".format(len(cell))
                    print("  [{}] {} = {}".format(i, header[i] if i < len(header) else "?", val))
                break

# Write just this one row as clean CSV and check
print("\n--- Clean CSV output for this row ---")
with open('/tmp/test_one_row.csv', 'w', newline='', encoding='utf-8') as out:
    writer = csv.writer(out, quoting=csv.QUOTE_ALL)
    writer.writerow(['c' + str(i) for i in range(49)])
    for f in files:
        with open(f, 'r', encoding='utf-8', errors='replace') as fh:
            reader = csv.reader(fh)
            next(reader)
            for row in reader:
                if row[0] == TARGET_UUID:
                    cleaned = [cell.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ') for cell in row[:49]]
                    writer.writerow(cleaned)
                    break

with open('/tmp/test_one_row.csv', 'r') as fh:
    lines = fh.readlines()
    print("Lines in output: {}".format(len(lines)))
    for i, line in enumerate(lines):
        print("Line {}: {} chars".format(i, len(line)))
        if i == 1:
            # Count commas outside quotes
            in_q = False
            commas = 0
            for ch in line:
                if ch == '"':
                    in_q = not in_q
                elif ch == ',' and not in_q:
                    commas += 1
            print("  Commas outside quotes: {} (expected 48)".format(commas))
