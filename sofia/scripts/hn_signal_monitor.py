#!/usr/bin/env python3
"""
OnSocial Signal Monitor — HN + News
Мониторит Hacker News и RSS-фиды новостей на предмет:
- "Who is Hiring" threads — компании из creator/influencer space
- Запуски продуктов (Show HN) связанные с creator economy
- Funding rounds упомянутые в новостях
- Упоминания конкурентов (HypeAuditor, Modash, GRIN, CreatorIQ)

Результат: JSON + Telegram алерт.
"""

import os
import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.path.expanduser("~/signal-monitor"))
DATA_DIR.mkdir(exist_ok=True)

SEEN_FILE = DATA_DIR / "seen_hn.json"
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "hn_monitor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Keywords & patterns
# ---------------------------------------------------------------------------

# Keywords that indicate creator/influencer space relevance
SIGNAL_KEYWORDS = [
    "influencer marketing", "influencer platform", "influencer analytics",
    "creator economy", "creator platform", "creator analytics", "creator data",
    "tiktok shop", "social commerce", "creator commerce",
    "instagram api", "tiktok api", "youtube api", "social media api",
    "white-label", "white label",
    "influencer discovery", "creator discovery",
    "ugc platform", "ugc marketplace",
    "affiliate creator", "creator monetization",
    "brand ambassador", "micro-influencer",
]

# Competitors — any mention is a signal
COMPETITOR_KEYWORDS = [
    "hypeauditor", "modash", "grin technologies", "creatoriq",
    "traackr", "upfluence", "aspire.io", "later influence",
    "klear", "meltwater social",
]

# Funding keywords
FUNDING_KEYWORDS = [
    "raised", "funding", "series a", "series b", "series c",
    "seed round", "pre-seed", "venture", "investment round",
    "acquired", "acquisition", "merger",
]

# ICP company names — direct mention = high priority
ICP_COMPANIES = [
    "kolsquare", "skeepers", "phyllo", "klugklug", "qoruz",
    "favikon", "tribegroup", "whalar", "billion dollar boy",
    "linkster", "ykone", "intermate", "ladbible",
    "impact.com", "partnerize", "awin",
    "sociata", "arabads", "cloutflow", "chtrbox",
    "tonic worldwide", "grynow", "confluencr",
]


# ---------------------------------------------------------------------------
# HN API functions
# ---------------------------------------------------------------------------

HN_API = "https://hacker-news.firebaseio.com/v0"


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)))


def get_item(item_id: int) -> dict:
    """Fetch a single HN item."""
    try:
        r = requests.get(f"{HN_API}/item/{item_id}.json", timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def search_hn_algolia(query: str, tags: str = "story", hits: int = 20) -> list:
    """Search HN via Algolia API."""
    try:
        r = requests.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={
                "query": query,
                "tags": tags,
                "hitsPerPage": hits,
                "numericFilters": "created_at_i>=" + str(int(datetime.now().timestamp()) - 172800),  # 48h
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("hits", [])
    except Exception as e:
        log.warning(f"Algolia search error for '{query}': {e}")
    return []


def classify_signal(text: str) -> dict:
    """Classify text for signal relevance."""
    text_lower = text.lower()

    matched_signals = [kw for kw in SIGNAL_KEYWORDS if kw in text_lower]
    matched_competitors = [kw for kw in COMPETITOR_KEYWORDS if kw in text_lower]
    matched_funding = [kw for kw in FUNDING_KEYWORDS if kw in text_lower]
    matched_icp = [c for c in ICP_COMPANIES if c in text_lower]

    score = len(matched_signals) * 2 + len(matched_competitors) * 3 + len(matched_funding) + len(matched_icp) * 5

    if matched_icp:
        category = "ICP_MENTION"
    elif matched_competitors:
        category = "COMPETITOR_INTEL"
    elif matched_funding and matched_signals:
        category = "FUNDING_SIGNAL"
    elif matched_signals:
        category = "INDUSTRY_NEWS"
    else:
        category = "NOISE"

    return {
        "score": score,
        "category": category,
        "matched_signals": matched_signals,
        "matched_competitors": matched_competitors,
        "matched_funding": matched_funding,
        "matched_icp": matched_icp,
    }


def send_telegram(message: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("Telegram not configured, skipping alert")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10,
        )
        if resp.status_code == 200:
            log.info("Telegram alert sent")
        else:
            log.warning(f"Telegram error: {resp.status_code}")
    except Exception as e:
        log.warning(f"Telegram failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_monitor():
    log.info("=" * 60)
    log.info("OnSocial HN + News Monitor - starting")
    log.info("=" * 60)

    seen = load_seen()
    signals = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Search HN for relevant stories
    search_queries = [
        "influencer marketing",
        "creator economy",
        "creator platform",
        "social commerce",
        "TikTok Shop",
        "influencer analytics",
        "creator data",
        "HypeAuditor",
        "Modash",
        "CreatorIQ",
    ]

    for query in search_queries:
        log.info(f"Searching HN: '{query}'")
        hits = search_hn_algolia(query, hits=10)

        for hit in hits:
            oid = hit.get("objectID", "")
            if oid in seen:
                continue
            seen.add(oid)

            title = hit.get("title", "") or ""
            url = hit.get("url", "") or ""
            story_text = hit.get("story_text", "") or ""
            full_text = f"{title} {story_text}"

            classification = classify_signal(full_text)

            if classification["category"] == "NOISE":
                continue

            signals.append({
                "date": today,
                "source": "HN",
                "category": classification["category"],
                "score": classification["score"],
                "title": title,
                "url": url or f"https://news.ycombinator.com/item?id={oid}",
                "matched_signals": ", ".join(classification["matched_signals"]),
                "matched_competitors": ", ".join(classification["matched_competitors"]),
                "matched_icp": ", ".join(classification["matched_icp"]),
                "hn_id": oid,
            })

    # 2. Check "Who is Hiring" - search for latest thread
    log.info("Checking Who is Hiring threads...")
    wih_hits = search_hn_algolia("who is hiring", tags="story", hits=3)
    for hit in wih_hits:
        title = hit.get("title", "")
        if "who is hiring" not in title.lower() and "ask hn: who is hiring" not in title.lower():
            continue

        oid = hit.get("objectID", "")
        if f"wih_{oid}" in seen:
            continue
        seen.add(f"wih_{oid}")

        log.info(f"  Found WiH thread: {title}")
        # Fetch comments (job postings)
        item = get_item(int(oid))
        kids = item.get("kids", [])[:100]  # first 100 comments

        for kid_id in kids:
            if str(kid_id) in seen:
                continue
            seen.add(str(kid_id))

            comment = get_item(kid_id)
            text = comment.get("text", "") or ""

            classification = classify_signal(text)
            if classification["category"] == "NOISE":
                continue

            # Extract company name from first line
            first_line = text.split("<")[0].split("|")[0].strip()[:100]

            signals.append({
                "date": today,
                "source": "HN_WhoIsHiring",
                "category": classification["category"],
                "score": classification["score"],
                "title": first_line,
                "url": f"https://news.ycombinator.com/item?id={kid_id}",
                "matched_signals": ", ".join(classification["matched_signals"]),
                "matched_competitors": ", ".join(classification["matched_competitors"]),
                "matched_icp": ", ".join(classification["matched_icp"]),
                "hn_id": str(kid_id),
            })

    save_seen(seen)

    if not signals:
        log.info("No new signals found")
        return

    # Save results
    signals.sort(key=lambda x: x["score"], reverse=True)

    results_file = RESULTS_DIR / f"hn_signals_{today}.json"
    with open(results_file, "w") as f:
        json.dump(signals, f, indent=2)
    log.info(f"Saved {len(signals)} signals to {results_file}")

    # Append to cumulative
    cumulative = RESULTS_DIR / "all_hn_signals.json"
    existing = []
    if cumulative.exists():
        existing = json.loads(cumulative.read_text())
    existing.extend(signals)
    cumulative.write_text(json.dumps(existing, indent=2))

    # Telegram summary
    summary = (
        f"<b>OnSocial HN Monitor</b>\n"
        f"Date: {today}\n\n"
        f"New signals: {len(signals)}\n"
    )

    by_cat = {}
    for s in signals:
        by_cat.setdefault(s["category"], []).append(s)

    for cat, items in sorted(by_cat.items()):
        summary += f"  {cat}: {len(items)}\n"

    top = signals[:5]
    if top:
        summary += "\n<b>Top signals:</b>\n"
        for s in top:
            summary += f"\n[{s['category']}] score={s['score']}\n  {s['title'][:80]}\n  {s['url']}\n"

    log.info(summary)
    send_telegram(summary)


if __name__ == "__main__":
    run_monitor()
