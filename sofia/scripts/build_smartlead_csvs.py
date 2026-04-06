#!/usr/bin/env python3.11
"""
Build SmartLead-ready CSVs from imagency_final_enriched.csv
- Maps hq_country -> geo_cluster -> custom1-4
- Outputs 3 CSVs: founders, creative, account_ops
- Also outputs excluded leads for GetSales
"""

import csv
import os

INPUT = "/tmp/imagency_final_enriched.csv"
OUT_DIR = "/tmp/smartlead_ready"

# Geo cluster mapping: country -> cluster key
# Based on agreed 6 clusters
COUNTRY_TO_CLUSTER = {
    # UK+IE
    "United Kingdom": "UK_IE",
    "Ireland": "UK_IE",
    # DACH+Nordics+NL+BE
    "Germany": "DACH_NORDICS",
    "Austria": "DACH_NORDICS",
    "Switzerland": "DACH_NORDICS",
    "Netherlands": "DACH_NORDICS",
    "Belgium": "DACH_NORDICS",
    "Sweden": "DACH_NORDICS",
    "Norway": "DACH_NORDICS",
    "Denmark": "DACH_NORDICS",
    "Finland": "DACH_NORDICS",
    # Southern EU
    "France": "SOUTHERN_EU",
    "Spain": "SOUTHERN_EU",
    "Italy": "SOUTHERN_EU",
    "Portugal": "SOUTHERN_EU",
    "Greece": "SOUTHERN_EU",
    # CEE+Turkey
    "Poland": "CEE_TURKEY",
    "Czech Republic": "CEE_TURKEY",
    "Slovakia": "CEE_TURKEY",
    "Hungary": "CEE_TURKEY",
    "Romania": "CEE_TURKEY",
    "Bulgaria": "CEE_TURKEY",
    "Croatia": "CEE_TURKEY",
    "Serbia": "CEE_TURKEY",
    "Ukraine": "CEE_TURKEY",
    "Turkey": "CEE_TURKEY",
    "Lithuania": "CEE_TURKEY",
    "Latvia": "CEE_TURKEY",
    "Estonia": "CEE_TURKEY",
    "Slovenia": "CEE_TURKEY",
    "Bosnia and Herzegovina": "CEE_TURKEY",
    "North Macedonia": "CEE_TURKEY",
    "Albania": "CEE_TURKEY",
    "Moldova": "CEE_TURKEY",
    "Belarus": "CEE_TURKEY",
    "Kosovo": "CEE_TURKEY",
    # India+APAC
    "India": "INDIA_APAC",
    "China": "INDIA_APAC",
    "Japan": "INDIA_APAC",
    "South Korea": "INDIA_APAC",
    "Singapore": "INDIA_APAC",
    "Australia": "INDIA_APAC",
    "New Zealand": "INDIA_APAC",
    "Indonesia": "INDIA_APAC",
    "Malaysia": "INDIA_APAC",
    "Thailand": "INDIA_APAC",
    "Vietnam": "INDIA_APAC",
    "Philippines": "INDIA_APAC",
    "Pakistan": "INDIA_APAC",
    "Bangladesh": "INDIA_APAC",
    # MENA+LATAM+Africa (catch-all for rest)
    "United Arab Emirates": "MENA_LATAM_AFRICA",
    "Saudi Arabia": "MENA_LATAM_AFRICA",
    "Egypt": "MENA_LATAM_AFRICA",
    "Morocco": "MENA_LATAM_AFRICA",
    "Nigeria": "MENA_LATAM_AFRICA",
    "South Africa": "MENA_LATAM_AFRICA",
    "Kenya": "MENA_LATAM_AFRICA",
    "Brazil": "MENA_LATAM_AFRICA",
    "Mexico": "MENA_LATAM_AFRICA",
    "Colombia": "MENA_LATAM_AFRICA",
    "Argentina": "MENA_LATAM_AFRICA",
    "Chile": "MENA_LATAM_AFRICA",
    "Peru": "MENA_LATAM_AFRICA",
    "Israel": "MENA_LATAM_AFRICA",
    "Jordan": "MENA_LATAM_AFRICA",
    "Lebanon": "MENA_LATAM_AFRICA",
    "Kuwait": "MENA_LATAM_AFRICA",
    "Qatar": "MENA_LATAM_AFRICA",
    "Bahrain": "MENA_LATAM_AFRICA",
    "Oman": "MENA_LATAM_AFRICA",
    "Tunisia": "MENA_LATAM_AFRICA",
    "Algeria": "MENA_LATAM_AFRICA",
    "Ghana": "MENA_LATAM_AFRICA",
    "Ethiopia": "MENA_LATAM_AFRICA",
    "Tanzania": "MENA_LATAM_AFRICA",
    "Uganda": "MENA_LATAM_AFRICA",
    "Ivory Coast": "MENA_LATAM_AFRICA",
    "Senegal": "MENA_LATAM_AFRICA",
}

# Default: fallback to MENA_LATAM_AFRICA for unknown
DEFAULT_CLUSTER = "MENA_LATAM_AFRICA"

# Custom field values per cluster and segment
# Structure: CLUSTER -> {custom1, custom2, custom3, custom4}
# Values vary by SEGMENT (founders/creative/account_ops) only for custom2 logic
# But per the sequences, custom1-4 are SHARED across segments within geo

GEO_FIELDS = {
    "UK_IE": {
        "custom1": "balancing influencer freedom with brand safety",
        "custom2": "Whalar, InfluencerUK, LADbible and Billion Dollar Boy",
        "custom3": "agencies moving off HypeAuditor over pricing transparency",
        "custom4": "UK agencies plan to scale creator programs 50%+ this year",
    },
    "DACH_NORDICS": {
        "custom1": "finding verified creators with reliable audience data",
        "custom2": "Zalando, Linkster, Intermate and Gocomo",
        "custom3": "analytics gaps in tools like HypeAuditor",
        "custom4": "51% of Nordic marketers say data reliability is their top challenge",
    },
    "SOUTHERN_EU": {
        "custom1": "facing rising influencer costs with no clear ROI proof",
        "custom2": "Kolsquare, Ykone, SAMYGroup and Favikon",
        "custom3": "tools that lack creator coverage outside Western Europe",
        "custom4": "IM budgets across Southern Europe are growing - but so is cost inflation",
    },
    "CEE_TURKEY": {
        "custom1": "verifying real engagement when fake followers are everywhere",
        "custom2": "Traackr, Audiense and Upfluence",
        "custom3": "global tools that lack depth in CEE and Turkish creator data",
        "custom4": "Buying popularity is easy - proving engagement is real is the hard part",
    },
    "INDIA_APAC": {
        "custom1": "protecting margins when clients ask to see the data source",
        "custom2": "Phyllo, KlugKlug, Qoruz and TRIBEGroup",
        "custom3": "paying for HypeAuditor while clients see their branding in your reports",
        "custom4": "IM agencies run on 15-25% margins - white-label data keeps clients seeing you as the source",
    },
    "MENA_LATAM_AFRICA": {
        "custom1": "getting reliable creator data across multiple markets from one source",
        "custom2": "ArabyAds and Sociata",
        "custom3": "stitching together 5+ data sources for multi-market campaigns",
        "custom4": "Running creator campaigns across markets means fragmented data - unless you have one API",
    },
}

# SmartLead required columns
SMARTLEAD_COLS = [
    "email",
    "first_name",
    "last_name",
    "company_name",
    "custom1",
    "custom2",
    "custom3",
    "custom4",
]

# GetSales columns (for excluded leads without email)
GETSALES_COLS = [
    "email",
    "first_name",
    "last_name",
    "company_name",
    "job_title",
    "linkedin_profile",
    "location",
]


def get_cluster(country: str) -> str:
    if not country or country.strip() in ("", "Unknown", "UNKNOWN"):
        return DEFAULT_CLUSTER
    return COUNTRY_TO_CLUSTER.get(country.strip(), DEFAULT_CLUSTER)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    founders = []
    creative = []
    account_ops = []
    excluded = []

    with open(INPUT, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cluster = row.get("dm_cluster", "").strip()
            country = row.get("hq_country", "").strip()
            geo_cluster = get_cluster(country)
            fields = GEO_FIELDS[geo_cluster]

            smartlead_row = {
                "email": row.get("email", ""),
                "first_name": row.get("first_name", ""),
                "last_name": row.get("last_name", ""),
                "company_name": row.get("company_name", ""),
                "custom1": fields["custom1"],
                "custom2": fields["custom2"],
                "custom3": fields["custom3"],
                "custom4": fields["custom4"],
            }

            getsales_row = {
                "email": row.get("email", ""),
                "first_name": row.get("first_name", ""),
                "last_name": row.get("last_name", ""),
                "company_name": row.get("company_name", ""),
                "job_title": row.get("job_title", ""),
                "linkedin_profile": row.get("linkedin_profile", ""),
                "location": row.get("location", ""),
            }

            if cluster == "FOUNDERS_CSUITE":
                founders.append(smartlead_row)
            elif cluster == "CREATIVE_LEADERSHIP":
                creative.append(smartlead_row)
            elif cluster == "ACCOUNT_OPS":
                account_ops.append(smartlead_row)
            elif cluster == "EXCLUDED":
                excluded.append(getsales_row)

    def write_csv(rows, path, cols):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} rows -> {path}")

    write_csv(founders, f"{OUT_DIR}/imagency_founders_smartlead.csv", SMARTLEAD_COLS)
    write_csv(creative, f"{OUT_DIR}/imagency_creative_smartlead.csv", SMARTLEAD_COLS)
    write_csv(
        account_ops, f"{OUT_DIR}/imagency_account_ops_smartlead.csv", SMARTLEAD_COLS
    )
    write_csv(excluded, f"{OUT_DIR}/imagency_excluded_getsales.csv", GETSALES_COLS)

    print("\nGeo distribution summary:")
    all_rows = founders + creative + account_ops
    from collections import Counter

    cluster_counts = Counter()
    for r in founders:
        cluster_counts[r["custom4"][:40]] += 1
    print(
        f"\nFounders ({len(founders)}), Creative ({len(creative)}), Account/Ops ({len(account_ops)}), Excluded ({len(excluded)})"
    )
    print(
        f"Total processed: {len(founders) + len(creative) + len(account_ops) + len(excluded)}"
    )


if __name__ == "__main__":
    main()
