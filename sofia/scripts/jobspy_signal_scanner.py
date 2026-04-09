#!/usr/bin/env python3
"""
OnSocial Signal Scanner — JobSpy
Ежедневный скан вакансий для обнаружения buying signals.

Сигналы:
- Компания нанимает data engineer / backend engineer → строят свой pipeline
- JD упоминает Instagram API, TikTok API, creator data → входят в creator space
- Influencer platform нанимает Head of Product / VP Eng → новый decision-maker
- IM agency нанимает Head of Partnerships → растут
- Affiliate platform нанимает Creator Partnerships → расширяются в creator space

Результат: CSV + Telegram алерт если есть новые сигналы.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from jobspy import scrape_jobs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.path.expanduser("~/jobspy-signals"))
DATA_DIR.mkdir(exist_ok=True)

SEEN_FILE = DATA_DIR / "seen_jobs.json"
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "scanner.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# Telegram config (optional)
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Search queries — each targets a different signal type
# ---------------------------------------------------------------------------

SEARCHES = [
    # SIGNAL 1: SaaS platforms building creator data infra
    {
        "name": "creator_data_infra",
        "segment": "INFPLAT",
        "signal": "Building creator data pipeline",
        "search_term": "creator data engineer",
        "why": "Company hiring data eng for creator/influencer data = building own pipeline",
    },
    {
        "name": "influencer_api_dev",
        "segment": "INFPLAT",
        "signal": "Instagram/TikTok API integration",
        "search_term": "Instagram API TikTok developer",
        "why": "Integrating social APIs = entering creator analytics space",
    },
    {
        "name": "influencer_platform_eng",
        "segment": "INFPLAT",
        "signal": "Influencer platform hiring engineers",
        "search_term": "influencer marketing platform engineer",
        "why": "Platform scaling engineering team = growth phase",
    },
    # SIGNAL 2: IM agencies growing
    {
        "name": "im_agency_partnerships",
        "segment": "IMAGENCY",
        "signal": "Agency hiring partnerships lead",
        "search_term": "influencer marketing agency head of partnerships",
        "why": "New partnerships role = agency expanding, needs tools",
    },
    {
        "name": "im_agency_hiring",
        "segment": "IMAGENCY",
        "signal": "IM agency scaling team",
        "search_term": "influencer marketing manager agency",
        "why": "Agency hiring IM managers = growing practice, needs analytics",
    },
    # SIGNAL 3: Affiliate platforms expanding into creator space
    {
        "name": "affiliate_creator",
        "segment": "AFFPERF",
        "signal": "Affiliate platform adding creator features",
        "search_term": "affiliate platform creator partnerships",
        "why": "Affiliate + creator convergence = need creator data API",
    },
    {
        "name": "creator_commerce",
        "segment": "AFFPERF",
        "signal": "Creator commerce / social selling",
        "search_term": "creator commerce social selling platform",
        "why": "Creator commerce companies need creator quality data",
    },
    # SIGNAL 4: Companies using competitor tools (displacement opportunity)
    {
        "name": "hypeauditor_users",
        "segment": "ALL",
        "signal": "Uses HypeAuditor (competitor)",
        "search_term": "HypeAuditor influencer marketing",
        "why": "Company mentioning competitor in JD = already buying, can displace",
    },
    # SIGNAL 5: Head of Product / VP Eng at creator companies (new decision-maker)
    {
        "name": "creator_leadership",
        "segment": "INFPLAT",
        "signal": "New product/eng leadership at creator company",
        "search_term": "VP engineering influencer creator platform",
        "why": "New VP/Head = reviews vendor stack in first 90 days",
    },
]

# Keywords that boost signal relevance when found in job description
BOOST_KEYWORDS = [
    "creator data", "influencer data", "creator analytics", "influencer analytics",
    "social media API", "Instagram API", "TikTok API", "YouTube API",
    "creator economy", "influencer platform", "creator platform",
    "white-label", "white label", "data pipeline", "data infrastructure",
    "HypeAuditor", "Modash", "GRIN", "CreatorIQ", "Traackr",
    "influencer discovery", "creator discovery", "audience analytics",
    "influencer marketing platform", "creator management",
    "social commerce", "TikTok Shop", "affiliate creator",
]

# Regions of interest (MENA+APAC and India convert best for OnSocial)
HIGH_PRIORITY_LOCATIONS = [
    "UAE", "Dubai", "Abu Dhabi", "Saudi", "Riyadh",
    "Singapore", "India", "Mumbai", "Bangalore", "Delhi",
    "Indonesia", "Jakarta", "Philippines", "Manila",
    "Thailand", "Bangkok", "Vietnam",
    "Australia", "Sydney", "Melbourne",
]

# Companies too large or irrelevant to be OnSocial ICP
EXCLUDE_COMPANIES = {
    "amazon.com", "amazon", "google", "meta", "microsoft", "apple",
    "netflix", "disney", "walmart", "target", "procter & gamble",
    "unilever", "coca-cola", "nike", "adidas",
    "tiktok", "bytedance", "instagram", "youtube", "snap", "snapchat",
    "pinterest", "twitter", "x corp",
    # OnSocial competitors (blacklist)
    "hypeauditor", "modash", "grin", "creatoriq", "traackr",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_seen() -> set:
    """Load previously seen job IDs to avoid duplicates."""
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)))


def job_hash(row) -> str:
    """Create a stable hash for deduplication."""
    raw = f"{row.get('title', '')}|{row.get('company', '')}|{row.get('location', '')}".lower()
    return hashlib.md5(raw.encode()).hexdigest()


def score_job(row) -> dict:
    """Score a job posting for signal relevance."""
    desc = str(row.get("description", "")).lower()
    title = str(row.get("title", "")).lower()
    company_desc = str(row.get("company_description", "")).lower()
    location = str(row.get("location", "")).lower()
    full_text = f"{desc} {title} {company_desc}"

    # Count keyword matches
    matched_keywords = [kw for kw in BOOST_KEYWORDS if kw.lower() in full_text]
    keyword_score = len(matched_keywords)

    # Check high-priority location
    is_priority_geo = any(loc.lower() in location for loc in HIGH_PRIORITY_LOCATIONS)

    # Determine urgency
    if keyword_score >= 4 and is_priority_geo:
        urgency = "CRITICAL"
    elif keyword_score >= 3 or (keyword_score >= 2 and is_priority_geo):
        urgency = "HIGH"
    elif keyword_score >= 1:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    return {
        "keyword_score": keyword_score,
        "matched_keywords": ", ".join(matched_keywords),
        "is_priority_geo": is_priority_geo,
        "urgency": urgency,
    }


def send_telegram(message: str):
    """Send alert to Telegram if configured."""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("Telegram not configured, skipping alert")
        return

    import requests

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info("Telegram alert sent")
        else:
            log.warning(f"Telegram error: {resp.status_code} {resp.text}")
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def run_scan():
    log.info("=" * 60)
    log.info("OnSocial Signal Scanner - starting")
    log.info("=" * 60)

    seen = load_seen()
    all_new_jobs = []
    today = datetime.now().strftime("%Y-%m-%d")

    # Worldwide: scan multiple Indeed country editions + LinkedIn (global)
    INDEED_COUNTRIES = [
        "USA", "UK", "India", "UAE", "Singapore",
        "Australia", "Germany", "France", "Netherlands",
        "Saudi Arabia", "Indonesia", "Philippines", "Thailand",
    ]

    for search in SEARCHES:
        log.info(f"Scanning: {search['name']} ({search['segment']})")
        try:
            # LinkedIn is global — one call covers worldwide
            all_frames = []
            try:
                li_jobs = scrape_jobs(
                    site_name=["linkedin"],
                    search_term=search["search_term"],
                    results_wanted=25,
                    hours_old=48,
                )
                if not li_jobs.empty:
                    all_frames.append(li_jobs)
            except Exception as e:
                log.warning(f"  LinkedIn error: {e}")

            # Indeed — per country
            for country in INDEED_COUNTRIES:
                try:
                    ij = scrape_jobs(
                        site_name=["indeed"],
                        search_term=search["search_term"],
                        results_wanted=10,
                        hours_old=48,
                        country_indeed=country,
                    )
                    if not ij.empty:
                        all_frames.append(ij)
                except Exception:
                    pass  # some countries may not have Indeed

            if all_frames:
                jobs = pd.concat(all_frames, ignore_index=True)
            else:
                jobs = pd.DataFrame()

            log.info(f"  Found {len(jobs)} raw results (LinkedIn + {len(INDEED_COUNTRIES)} Indeed countries)")

            if jobs.empty:
                continue

            for _, row in jobs.iterrows():
                jid = job_hash(row)
                if jid in seen:
                    continue

                seen.add(jid)

                # Skip mega-corps — not OnSocial ICP
                emp = str(row.get("company_num_employees", ""))
                company = str(row.get("company", "")).lower()
                if (
                    "10,000" in emp
                    or company in EXCLUDE_COMPANIES
                ):
                    continue

                scoring = score_job(row)

                if scoring["urgency"] == "LOW":
                    continue

                all_new_jobs.append({
                    "date": today,
                    "search_name": search["name"],
                    "segment": search["segment"],
                    "signal": search["signal"],
                    "urgency": scoring["urgency"],
                    "keyword_score": scoring["keyword_score"],
                    "matched_keywords": scoring["matched_keywords"],
                    "priority_geo": scoring["is_priority_geo"],
                    "title": row.get("title", ""),
                    "company": row.get("company", ""),
                    "location": row.get("location", ""),
                    "date_posted": str(row.get("date_posted", "")),
                    "job_url": row.get("job_url", ""),
                    "company_url": row.get("company_url", ""),
                    "company_employees": row.get("company_num_employees", ""),
                    "company_industry": row.get("company_industry", ""),
                })

        except Exception as e:
            log.error(f"  Error scanning {search['name']}: {e}")
            continue

    save_seen(seen)

    if not all_new_jobs:
        log.info("No new signals found today")
        return

    # Save results
    df = pd.DataFrame(all_new_jobs)
    df = df.sort_values(["urgency", "keyword_score"], ascending=[True, False])

    csv_path = RESULTS_DIR / f"signals_{today}.csv"
    df.to_csv(csv_path, index=False)
    log.info(f"Saved {len(df)} new signals to {csv_path}")

    # Also append to cumulative file
    cumulative = RESULTS_DIR / "all_signals.csv"
    if cumulative.exists():
        df.to_csv(cumulative, mode="a", header=False, index=False)
    else:
        df.to_csv(cumulative, index=False)

    # Summary stats
    critical = df[df["urgency"] == "CRITICAL"]
    high = df[df["urgency"] == "HIGH"]
    medium = df[df["urgency"] == "MEDIUM"]

    summary = (
        f"<b>OnSocial Signal Scanner</b>\n"
        f"Date: {today}\n\n"
        f"New signals: {len(df)}\n"
        f"  CRITICAL: {len(critical)}\n"
        f"  HIGH: {len(high)}\n"
        f"  MEDIUM: {len(medium)}\n"
    )

    # Add top signals to message
    top = df[df["urgency"].isin(["CRITICAL", "HIGH"])].head(5)
    if not top.empty:
        summary += "\n<b>Top signals:</b>\n"
        for _, row in top.iterrows():
            summary += (
                f"\n[{row['urgency']}] {row['segment']}\n"
                f"  {row['company']} - {row['title']}\n"
                f"  {row['location']}\n"
                f"  Signal: {row['signal']}\n"
                f"  Keywords: {row['matched_keywords']}\n"
                f"  {row['job_url']}\n"
            )

    log.info(summary)
    send_telegram(summary)


if __name__ == "__main__":
    run_scan()
