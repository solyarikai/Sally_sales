#!/usr/bin/env python3
import csv, glob, os
EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'getsales_exports')
files = sorted(glob.glob(os.path.join(EXPORT_DIR, 'contacts_export_*.csv')))
row_num = 0
for f in files:
    with open(f, 'r', encoding='utf-8', errors='replace') as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            row_num += 1
            if row_num >= 11405 and row_num <= 11410:
                print("Row {}: {} cols, uuid={}".format(row_num, len(row), row[0][:36] if row else ""))
                if len(row) != 49:
                    for i, cell in enumerate(row):
                        print("  col[{}]={}".format(i, repr(cell[:100])))
