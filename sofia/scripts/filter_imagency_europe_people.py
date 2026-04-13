"""Filter Apollo people JSON by tech/product/data title include + exclude lists."""

import json
import csv
import re
import sys
from pathlib import Path

INCLUDE_TITLES = [
    "CTO",
    "Chief Technology Officer",
    "CIO",
    "Chief Information Officer",
    "CPO",
    "Chief Product Officer",
    "CDO",
    "Chief Data Officer",
    "Chief Digital Officer",
    "VP Engineering",
    "VP of Engineering",
    "VP Technology",
    "VP Product",
    "VP of Product",
    "VP Data",
    "VP Analytics",
    "VP Platform",
    "SVP Engineering",
    "SVP Product",
    "SVP Technology",
    "Head of Engineering",
    "Head of Technology",
    "Head of Product",
    "Head of Data",
    "Head of Analytics",
    "Head of Platform",
    "Head of Integrations",
    "Head of Innovation",
    "Head of Digital",
    "Director of Engineering",
    "Director of Technology",
    "Director of Product",
    "Director of Data",
    "Director of Analytics",
    "Director of Platform",
    "Technical Director",
    "Technology Director",
    "Engineering Manager",
    "Tech Lead",
    "Technical Lead",
    "Solutions Architect",
    "Principal Architect",
    "Chief Architect",
    "Platform Lead",
    "Integration Lead",
    "Head of Martech",
    "Director of Martech",
    "Co-Founder CTO",
    "Founding Engineer",
    "Technical Co-Founder",
]

EXCLUDE_TITLES = [
    "Intern",
    "Junior",
    "Assistant",
    "Student",
    "Freelance",
    "IT Support",
    "IT Manager",
    "IT Administrator",
    "Desktop Support",
    "Systems Administrator",
    "Network Administrator",
    "Help Desk",
    "Helpdesk",
    "Marketing Technology Manager",
    "MarTech Manager",
    "Content Creator",
    "Designer",
    "UX Designer",
    "UI Designer",
    "QA Engineer",
    "Junior Engineer",
    "Software Tester",
    "HR",
    "People",
    "Recruiter",
    "Finance",
    "Accounting",
    "Social Media Manager",
    "Community Manager",
    "Campaign Manager",
    "Campaign Coordinator",
    "Account Manager",
    "Account Executive",
    "Sales",
    "Office Manager",
    "Executive Assistant",
]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def title_matches(title: str, patterns: list[str]) -> bool:
    t = norm(title)
    for p in patterns:
        np = norm(p)
        # word-boundary contains: ensure the pattern appears as whole token sequence
        if re.search(rf"(^|\b){re.escape(np)}(\b|$)", t):
            return True
    return False


def main(in_path: str, out_json: str, out_csv: str):
    data = json.loads(Path(in_path).read_text())
    print(f"Loaded {len(data)} records from {in_path}")

    kept = []
    excluded_count = 0
    no_include_match = 0
    for p in data:
        title = p.get("title", "")
        if not title:
            continue
        if title_matches(title, EXCLUDE_TITLES):
            excluded_count += 1
            continue
        if not title_matches(title, INCLUDE_TITLES):
            no_include_match += 1
            continue
        kept.append(p)

    print(f"Excluded by title: {excluded_count}")
    print(f"No include match: {no_include_match}")
    print(f"Kept: {len(kept)}")

    Path(out_json).write_text(json.dumps(kept, indent=2))

    if kept:
        fields = list(kept[0].keys())
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in kept:
                w.writerow(r)

    companies = len({p.get("domain") for p in kept if p.get("domain")})
    print(f"Companies covered: {companies}")
    print(f"Output JSON: {out_json}")
    print(f"Output CSV: {out_csv}")


if __name__ == "__main__":
    in_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "/Users/user/sales_engineer/sofia/input/imagency_europe_people.json"
    )
    out_json = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "/Users/user/sales_engineer/sofia/input/imagency_europe_people_filtered.json"
    )
    out_csv = (
        sys.argv[3]
        if len(sys.argv) > 3
        else "/Users/user/sales_engineer/sofia/input/imagency_europe_people_filtered.csv"
    )
    main(in_path, out_json, out_csv)
