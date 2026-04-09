#!/usr/bin/env python3
"""
OnSocial Signal Monitor — GitHub
Мониторит GitHub организации целевых компаний:
- Новые репозитории (новый продукт / пивот)
- Рост команды (новые контрибуторы)
- Tech stack changes (новые языки / фреймворки)
- Активность (всплеск коммитов = development sprint)

Работает на бесплатном GitHub API (5000 req/hr с токеном, 60 req/hr без).
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.path.expanduser("~/signal-monitor"))
DATA_DIR.mkdir(exist_ok=True)

SEEN_FILE = DATA_DIR / "seen_github.json"
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "github_monitor.log"

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
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# GitHub API headers
GH_HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    GH_HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

GH_API = "https://api.github.com"

# ---------------------------------------------------------------------------
# Target GitHub organizations
# ---------------------------------------------------------------------------

# Map: company name -> GitHub org(s)
# Found by searching GitHub for known company names
TARGET_ORGS = {
    # ICP - INFPLAT
    "Kolsquare": ["kolsquare"],
    "Phyllo": ["nicejob", "getphyllo"],
    "Modash (competitor)": ["modash-io"],
    "HypeAuditor (competitor)": ["hypeauditor"],
    "CreatorIQ (competitor)": ["creatoriq"],
    "Traackr (competitor)": ["traackr"],
    "GRIN (competitor)": ["gaboratorium"],  # placeholder
    "Upfluence (competitor)": ["upfluence"],
    # ICP - AFFPERF
    "impact.com": ["nicejob", "nicejob"],
    # Other known orgs in creator space
    "Later": ["later"],
    "Aspire.io": ["aspireio"],
    "Klear": ["kabortech"],
    # India ICP
    "Qoruz": ["qoruz"],
    "KlugKlug": ["klugklug"],
    "Tonic Worldwide": ["tonicworldwide"],
}

# Keywords in repo names/descriptions that indicate creator/influencer features
RELEVANT_KEYWORDS = [
    "influencer", "creator", "social", "instagram", "tiktok", "youtube",
    "analytics", "api", "data", "pipeline", "scraper", "crawler",
    "white-label", "whitelabel", "dashboard", "embed",
    "affiliate", "ugc", "commerce",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen: dict):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def gh_get(path: str) -> dict | list | None:
    """Make a GitHub API request."""
    try:
        r = requests.get(f"{GH_API}{path}", headers=GH_HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 403:
            log.warning("GitHub rate limit hit")
            return None
        else:
            return None
    except Exception as e:
        log.warning(f"GitHub API error: {e}")
        return None


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
    except Exception as e:
        log.warning(f"Telegram failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_monitor():
    log.info("=" * 60)
    log.info("OnSocial GitHub Monitor - starting")
    log.info("=" * 60)

    seen = load_seen()
    signals = []
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()

    for company, orgs in TARGET_ORGS.items():
        for org_name in orgs:
            log.info(f"Checking: {company} ({org_name})")

            # 1. Check for new repos
            repos = gh_get(f"/orgs/{org_name}/repos?sort=created&per_page=10")
            if repos is None:
                repos = gh_get(f"/users/{org_name}/repos?sort=created&per_page=10")
            if not repos:
                continue

            prev_repos = set(seen.get(f"{org_name}_repos", []))
            current_repos = set()

            for repo in repos:
                repo_name = repo.get("full_name", "")
                current_repos.add(repo_name)
                created = repo.get("created_at", "")
                description = (repo.get("description", "") or "").lower()
                name_lower = repo_name.lower()

                # New repo check
                if repo_name not in prev_repos and created > cutoff:
                    is_relevant = any(kw in name_lower or kw in description for kw in RELEVANT_KEYWORDS)

                    signals.append({
                        "date": today,
                        "source": "GitHub",
                        "company": company,
                        "org": org_name,
                        "signal_type": "NEW_REPO",
                        "repo": repo_name,
                        "description": repo.get("description", ""),
                        "language": repo.get("language", ""),
                        "url": repo.get("html_url", ""),
                        "is_relevant": is_relevant,
                        "stars": repo.get("stargazers_count", 0),
                    })

            seen[f"{org_name}_repos"] = list(current_repos)

            # 2. Check org members count (team growth signal)
            org_info = gh_get(f"/orgs/{org_name}")
            if org_info:
                public_repos = org_info.get("public_repos", 0)
                members_url = org_info.get("members_url", "")
                prev_repos_count = seen.get(f"{org_name}_repo_count", 0)

                if prev_repos_count > 0 and public_repos > prev_repos_count + 2:
                    signals.append({
                        "date": today,
                        "source": "GitHub",
                        "company": company,
                        "org": org_name,
                        "signal_type": "REPO_GROWTH",
                        "detail": f"Repos grew from {prev_repos_count} to {public_repos}",
                        "url": f"https://github.com/{org_name}",
                        "is_relevant": True,
                    })

                seen[f"{org_name}_repo_count"] = public_repos

    save_seen(seen)

    if not signals:
        log.info("No new GitHub signals")
        return

    # Save results
    results_file = RESULTS_DIR / f"github_signals_{today}.json"
    with open(results_file, "w") as f:
        json.dump(signals, f, indent=2)
    log.info(f"Saved {len(signals)} GitHub signals")

    # Append to cumulative
    cumulative = RESULTS_DIR / "all_github_signals.json"
    existing = []
    if cumulative.exists():
        existing = json.loads(cumulative.read_text())
    existing.extend(signals)
    cumulative.write_text(json.dumps(existing, indent=2))

    # Telegram
    relevant = [s for s in signals if s.get("is_relevant")]
    summary = (
        f"<b>OnSocial GitHub Monitor</b>\n"
        f"Date: {today}\n\n"
        f"Total signals: {len(signals)}\n"
        f"Relevant: {len(relevant)}\n"
    )

    for s in relevant[:5]:
        summary += f"\n[{s.get('signal_type')}] {s.get('company')}\n"
        if s.get("repo"):
            summary += f"  {s['repo']}: {s.get('description', '')[:60]}\n"
        if s.get("detail"):
            summary += f"  {s['detail']}\n"
        summary += f"  {s.get('url', '')}\n"

    log.info(summary)
    send_telegram(summary)


if __name__ == "__main__":
    run_monitor()
