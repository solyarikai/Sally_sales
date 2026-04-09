#!/usr/bin/env python3
"""
OnSocial Signal Monitor — RSS News Feeds
Поллит бесплатные RSS-фиды и Google Alerts RSS на предмет:
- Funding rounds компаний из creator/influencer space
- Запуски продуктов
- M&A
- Упоминания ICP и конкурентов

Feeds:
- TechCrunch (funding, startups)
- ProductHunt (launches)
- Google Alerts RSS (если настроены)
- Custom RSS feeds

Результат: JSON + Telegram алерт.
"""

import os
import json
import logging
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from html import unescape
import re

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.path.expanduser("~/signal-monitor"))
DATA_DIR.mkdir(exist_ok=True)

SEEN_FILE = DATA_DIR / "seen_rss.json"
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "rss_monitor.log"

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
# RSS Feeds
# ---------------------------------------------------------------------------

# Google News RSS — search-based feeds (no setup needed, free)
GOOGLE_NEWS_QUERIES = [
    "influencer marketing platform funding",
    "creator economy startup raised",
    "influencer analytics acquisition",
    "social commerce platform funding",
    "creator platform series",
    "TikTok Shop partner platform",
    "influencer marketing agency acquisition",
    "HypeAuditor OR Modash OR CreatorIQ OR Traackr",
    "white label influencer",
]

# Direct RSS feeds
RSS_FEEDS = [
    # ProductHunt — new launches
    ("ProductHunt", "https://www.producthunt.com/feed?category=marketing"),
    # TechCrunch — funding
    ("TechCrunch", "https://techcrunch.com/category/startups/feed/"),
]

# Google Alerts RSS — add here after creating alerts
# To create: https://www.google.com/alerts → create alert → choose RSS delivery
GOOGLE_ALERTS_RSS = [
    # ("alert_name", "https://www.google.com/alerts/feeds/..."),
]

# Keywords for relevance filtering
SIGNAL_KEYWORDS = [
    "influencer", "creator economy", "creator platform", "creator analytics",
    "influencer marketing", "influencer platform", "social commerce",
    "tiktok shop", "creator data", "ugc", "brand ambassador",
    "white-label", "white label", "influencer discovery",
    "creator monetization", "affiliate creator",
]

COMPETITOR_KEYWORDS = [
    "hypeauditor", "modash", "grin", "creatoriq", "traackr",
    "upfluence", "aspire", "klear", "later influence",
]

ICP_COMPANIES = [
    "kolsquare", "skeepers", "phyllo", "klugklug", "qoruz",
    "favikon", "tribegroup", "whalar", "billion dollar boy",
    "impact.com", "partnerize", "sociata", "cloutflow", "chtrbox",
]

FUNDING_KEYWORDS = [
    "raised", "funding", "series a", "series b", "series c",
    "seed round", "venture", "acquired", "acquisition", "ipo",
    "valuation", "investment",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)))


def item_hash(title: str, link: str) -> str:
    return hashlib.md5(f"{title}|{link}".encode()).hexdigest()


def strip_html(text: str) -> str:
    """Remove HTML tags."""
    clean = re.sub(r"<[^>]+>", " ", unescape(text))
    return re.sub(r"\s+", " ", clean).strip()


def parse_rss(xml_text: str) -> list:
    """Parse RSS/Atom feed, return list of items."""
    items = []
    try:
        root = ET.fromstring(xml_text)
        # Handle RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            desc = strip_html(item.findtext("description", ""))
            pub_date = item.findtext("pubDate", "")
            items.append({"title": title, "link": link, "description": desc, "pub_date": pub_date})

        # Handle Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            desc = strip_html(entry.findtext("atom:content", "", ns) or entry.findtext("atom:summary", "", ns))
            pub_date = entry.findtext("atom:published", "", ns) or entry.findtext("atom:updated", "", ns)
            items.append({"title": title, "link": link, "description": desc, "pub_date": pub_date})
    except ET.ParseError as e:
        log.warning(f"XML parse error: {e}")
    return items


def classify(text: str) -> dict:
    text_lower = text.lower()
    matched_signals = [kw for kw in SIGNAL_KEYWORDS if kw in text_lower]
    matched_competitors = [kw for kw in COMPETITOR_KEYWORDS if kw in text_lower]
    matched_icp = [c for c in ICP_COMPANIES if c in text_lower]
    matched_funding = [kw for kw in FUNDING_KEYWORDS if kw in text_lower]

    score = len(matched_signals) * 2 + len(matched_competitors) * 3 + len(matched_icp) * 5 + len(matched_funding)

    if matched_icp:
        cat = "ICP_MENTION"
    elif matched_competitors:
        cat = "COMPETITOR_INTEL"
    elif matched_funding and matched_signals:
        cat = "FUNDING_SIGNAL"
    elif matched_signals:
        cat = "INDUSTRY_NEWS"
    else:
        cat = "NOISE"

    return {
        "score": score,
        "category": cat,
        "matched_signals": matched_signals,
        "matched_competitors": matched_competitors,
        "matched_icp": matched_icp,
        "matched_funding": matched_funding,
    }


def send_telegram(message: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("Telegram not configured, skipping")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_monitor():
    log.info("=" * 60)
    log.info("OnSocial RSS Signal Monitor - starting")
    log.info("=" * 60)

    seen = load_seen()
    signals = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Google News RSS searches (no setup needed)
    for query in GOOGLE_NEWS_QUERIES:
        log.info(f"Google News: '{query}'")
        try:
            url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en&gl=US&ceid=US:en"
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue

            items = parse_rss(r.text)
            for item in items[:10]:
                h = item_hash(item["title"], item["link"])
                if h in seen:
                    continue
                seen.add(h)

                full_text = f"{item['title']} {item['description']}"
                cl = classify(full_text)

                if cl["category"] == "NOISE":
                    continue

                signals.append({
                    "date": today,
                    "source": "GoogleNews",
                    "query": query,
                    "category": cl["category"],
                    "score": cl["score"],
                    "title": item["title"],
                    "url": item["link"],
                    "description": item["description"][:200],
                    "matched": ", ".join(cl["matched_signals"] + cl["matched_competitors"] + cl["matched_icp"]),
                })
        except Exception as e:
            log.warning(f"Google News error for '{query}': {e}")

    # 2. Direct RSS feeds
    for feed_name, feed_url in RSS_FEEDS + GOOGLE_ALERTS_RSS:
        log.info(f"RSS: {feed_name}")
        try:
            r = requests.get(feed_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue

            items = parse_rss(r.text)
            for item in items[:15]:
                h = item_hash(item["title"], item["link"])
                if h in seen:
                    continue
                seen.add(h)

                full_text = f"{item['title']} {item['description']}"
                cl = classify(full_text)

                if cl["category"] == "NOISE":
                    continue

                signals.append({
                    "date": today,
                    "source": feed_name,
                    "category": cl["category"],
                    "score": cl["score"],
                    "title": item["title"],
                    "url": item["link"],
                    "description": item["description"][:200],
                    "matched": ", ".join(cl["matched_signals"] + cl["matched_competitors"] + cl["matched_icp"]),
                })
        except Exception as e:
            log.warning(f"RSS error for {feed_name}: {e}")

    save_seen(seen)

    if not signals:
        log.info("No new RSS signals")
        return

    signals.sort(key=lambda x: x["score"], reverse=True)

    # Save
    results_file = RESULTS_DIR / f"rss_signals_{today}.json"
    with open(results_file, "w") as f:
        json.dump(signals, f, indent=2)
    log.info(f"Saved {len(signals)} RSS signals")

    # Cumulative
    cumulative = RESULTS_DIR / "all_rss_signals.json"
    existing = []
    if cumulative.exists():
        existing = json.loads(cumulative.read_text())
    existing.extend(signals)
    cumulative.write_text(json.dumps(existing, indent=2))

    # Telegram
    summary = f"<b>OnSocial RSS Monitor</b>\nDate: {today}\n\nNew signals: {len(signals)}\n"

    by_cat = {}
    for s in signals:
        by_cat.setdefault(s["category"], []).append(s)
    for cat, items in sorted(by_cat.items()):
        summary += f"  {cat}: {len(items)}\n"

    top = signals[:5]
    if top:
        summary += "\n<b>Top:</b>\n"
        for s in top:
            summary += f"\n[{s['category']}] {s['title'][:70]}\n  {s['url']}\n"

    log.info(summary)
    send_telegram(summary)


if __name__ == "__main__":
    run_monitor()
