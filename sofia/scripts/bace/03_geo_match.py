#!/usr/bin/env python3
"""
Geo match — fill Company Country / City / # Employees from discovered_companies.

Input: any CSV with 'Website' column (domain).
Output: same CSV in-place (or --out) with 3 geo fields populated where empty.

Usage:
    python3 03_geo_match.py <input.csv> [--project-id 42] [--out output.csv]
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg2


def _db_conn():
    raw = os.environ.get("DATABASE_URL", "")
    url = (
        raw.replace("@leadgen-postgres:", "@localhost:")
        if raw
        else "postgresql://leadgen:leadgen_secret@localhost:5432/leadgen"
    )
    return psycopg2.connect(url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Input CSV (with Website column)")
    ap.add_argument("--project-id", type=int, default=42)
    ap.add_argument("--out", help="Output CSV (default: in-place)")
    args = ap.parse_args()

    in_path = Path(args.csv)
    out_path = Path(args.out) if args.out else in_path

    with in_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if not rows:
        print("  No rows.")
        sys.exit(0)

    domains = list({r.get("Website", "").strip() for r in rows if r.get("Website")})
    if not domains:
        print("  No domains in CSV.")
        sys.exit(0)

    conn = _db_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                domain,
                COALESCE(
                    NULLIF(country, ''),
                    NULLIF(company_info->>'country', ''),
                    NULLIF(apollo_org_data->>'country', '')
                ) AS country,
                COALESCE(
                    NULLIF(city, ''),
                    NULLIF(company_info->>'city', ''),
                    NULLIF(apollo_org_data->>'city', '')
                ) AS city,
                COALESCE(
                    NULLIF(employee_range, ''),
                    NULLIF(company_info->>'employees', ''),
                    NULLIF(apollo_org_data->>'estimated_num_employees', ''),
                    CASE WHEN employee_count > 0 THEN employee_count::text ELSE NULL END
                ) AS employees
            FROM discovered_companies
            WHERE domain = ANY(%s) AND project_id = %s
            """,
            (domains, args.project_id),
        )
        geo_map = {
            row[0]: {
                "country": row[1] or "",
                "city": row[2] or "",
                "employees": row[3] or "",
            }
            for row in cur.fetchall()
        }
    conn.close()

    for col in ["Company Country", "City", "# Employees"]:
        if col not in fieldnames:
            fieldnames.append(col)

    filled_country = filled_city = filled_emp = 0
    for row in rows:
        geo = geo_map.get(row.get("Website", "").strip(), {})
        if not row.get("Company Country") and geo.get("country"):
            row["Company Country"] = geo["country"]
            filled_country += 1
        if not row.get("City") and geo.get("city"):
            row["City"] = geo["city"]
            filled_city += 1
        if not row.get("# Employees") and geo.get("employees"):
            row["# Employees"] = geo["employees"]
            filled_emp += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    hits = len([d for d in domains if d in geo_map])
    print(
        f"  ✓ Geo-match: {hits}/{len(domains)} domains matched in DB | "
        f"filled: country={filled_country}/{total} city={filled_city}/{total} emp={filled_emp}/{total}"
    )
    print(f"  ✓ Saved → {out_path}")


if __name__ == "__main__":
    main()
