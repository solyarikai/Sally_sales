#!/usr/bin/env python3
"""
TFP Full Scrape — scrape ALL companies across all 7 country runs.

- Skips companies that already have scraped_text >= 200 chars (good scrape)
- Expires bad/empty scrapes and re-scrapes them
- Uses Apify residential proxy
- Saves progress every 100 companies
- After each run is fully scraped, triggers re-analyze via API

Runs inside the Docker container:
  docker exec -d leadgen-backend bash -c 'DATABASE_URL=... python3 /scripts/tfp_scrape_full.py'
"""

import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
RUNS = {21: "Italy", 24: "France", 27: "Germany", 42: "UK", 44: "Belgium", 46: "DACH", 47: "CEE"}
MIN_TEXT_LEN = 200          # below this = bad scrape, will re-scrape
CONCURRENCY = 8             # parallel requests
SAVE_EVERY = 100            # save progress every N companies
TIMEOUT = 15                # per-request timeout seconds
PROGRESS_FILE = "/tmp/tfp_scrape_progress.json"
API_BASE = "http://localhost:8000"
API_HEADERS = {"X-Company-ID": "1"}

ICP_PROMPT = (
    "TFP targets European D2C fashion brands with own collections. "
    "Target: fashion/apparel/footwear/accessories brand, own products, D2C or hybrid, "
    "5-500 employees, European. "
    "Not target: pure retailer, marketplace, no own brand, non-fashion, "
    "Polish brand, Netherlands/Dutch brand."
)

DB_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen_secret@postgres:5432/leadgen")
DB_URL = DB_URL.replace("+asyncpg", "")

APIFY_PASS = os.environ.get("APIFY_PROXY_PASSWORD", "")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# ── Progress ───────────────────────────────────────────────────────────────────
def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"scraped_ids": [], "failed_ids": [], "analyze_triggered": []}

def save_progress(state):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f)

# ── DB helpers ─────────────────────────────────────────────────────────────────
def get_companies_needing_scrape(conn, run_ids):
    """Get all companies that need (re-)scraping: no scrape or scraped_text < MIN_TEXT_LEN."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT dc.id, dc.domain, dc.first_found_by as run_id,
                   dc.scraped_text,
                   cs.id as scrape_id, cs.scrape_status
            FROM discovered_companies dc
            LEFT JOIN company_scrapes cs ON cs.discovered_company_id = dc.id
                AND cs.is_current = true AND cs.page_path = '/'
            WHERE dc.first_found_by = ANY(%s)
              AND dc.domain IS NOT NULL
              AND (
                dc.scraped_text IS NULL
                OR LENGTH(dc.scraped_text) < %s
              )
            ORDER BY dc.first_found_by, dc.id
        """, (run_ids, MIN_TEXT_LEN))
        return cur.fetchall()

def expire_old_scrape(conn, dc_id):
    """Mark existing scrape records as not current so we can insert a fresh one."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE company_scrapes
            SET is_current = false
            WHERE discovered_company_id = %s AND is_current = true AND page_path = '/'
        """, (dc_id,))
    conn.commit()

def strip_nul(s):
    """Remove NUL bytes that PostgreSQL rejects."""
    return s.replace("\x00", "") if s else s

def save_scrape_result(conn, dc_id, domain, text, raw_html, status_code, success, error_msg):
    """Insert new company_scrape record and update discovered_companies.scraped_text."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=180)

    # Get next version
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(version), 0) FROM company_scrapes WHERE discovered_company_id = %s AND page_path = '/'", (dc_id,))
        next_ver = cur.fetchone()[0] + 1

    clean = strip_nul(text[:50000]) if text else None
    html = strip_nul(raw_html[:100000]) if raw_html else None

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO company_scrapes (
                discovered_company_id, url, page_path, raw_html, clean_text,
                page_metadata, scraped_at, ttl_days, expires_at, is_current,
                version, scrape_method, scrape_status, error_message,
                http_status_code, html_size_bytes, text_size_bytes
            ) VALUES (%s,%s,'/',  %s,%s,
                %s, %s, 180, %s, true,
                %s, 'httpx', %s, %s,
                %s, %s, %s)
        """, (
            dc_id, f"https://{domain}", html, clean,
            json.dumps({"status_code": status_code}),
            now, expires_at,
            next_ver,
            "success" if success else "error",
            error_msg,
            status_code,
            len(raw_html) if raw_html else 0,
            len(text) if text else 0,
        ))
        if clean:
            cur.execute("""
                UPDATE discovered_companies
                SET scraped_text = %s, scraped_at = %s
                WHERE id = %s
            """, (clean, now, dc_id))
    conn.commit()

def get_run_phase(conn, run_id):
    with conn.cursor() as cur:
        cur.execute("SELECT current_phase FROM gathering_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
        return row[0] if row else None

def set_run_phase(conn, run_id, phase):
    with conn.cursor() as cur:
        cur.execute("UPDATE gathering_runs SET current_phase = %s WHERE id = %s", (phase, run_id))
    conn.commit()

def count_unscraped(conn, run_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM discovered_companies dc
            WHERE dc.first_found_by = %s
              AND (dc.scraped_text IS NULL OR LENGTH(dc.scraped_text) < %s)
        """, (run_id, MIN_TEXT_LEN))
        return cur.fetchone()[0]

# ── HTTP scraping ──────────────────────────────────────────────────────────────
def get_proxy():
    if not APIFY_PASS:
        return None
    sid = f"tfp_{random.randint(10000, 99999)}"
    return f"http://groups-RESIDENTIAL,session-{sid}:{APIFY_PASS}@proxy.apify.com:8000"

def extract_text(html: str) -> str:
    """Strip HTML tags and extract readable text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:50000]

async def fetch_url(domain: str, semaphore: asyncio.Semaphore) -> dict:
    """Fetch a domain's homepage and return {success, text, html, status_code, error}."""
    url = f"https://{domain}"
    proxy = get_proxy()
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "en-US,en;q=0.9"}

    async with semaphore:
        for scheme in ["https://", "http://"]:
            try_url = scheme + domain
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(TIMEOUT),
                    follow_redirects=True,
                    verify=False,
                    proxy=proxy,
                ) as client:
                    resp = await client.get(try_url, headers=headers)
                    html = resp.text
                    text = extract_text(html)
                    return {
                        "success": resp.status_code < 400,
                        "text": text,
                        "html": html,
                        "status_code": resp.status_code,
                        "error": None,
                    }
            except httpx.TimeoutException:
                if scheme == "https://":
                    continue
                return {"success": False, "text": "", "html": "", "status_code": None, "error": "TIMEOUT"}
            except Exception as e:
                if scheme == "https://":
                    continue
                return {"success": False, "text": "", "html": "", "status_code": None, "error": str(e)[:200]}
    return {"success": False, "text": "", "html": "", "status_code": None, "error": "ALL_FAILED"}

# ── Analyze trigger ────────────────────────────────────────────────────────────
def trigger_analyze(run_id, state):
    if run_id in state["analyze_triggered"]:
        return
    phase = get_run_phase(psycopg2.connect(DB_URL, cursor_factory=RealDictCursor), run_id)
    log.info(f"  Triggering analyze for run {run_id} ({RUNS[run_id]}, phase={phase})...")

    # For runs past "scraped", temporarily set to "scraped" so analyze endpoint accepts it
    conn2 = psycopg2.connect(DB_URL)
    if phase not in ("scraped", "filtered"):
        # Use re-analyze endpoint for runs at CP2+
        endpoint = f"{API_BASE}/api/pipeline/gathering/runs/{run_id}/re-analyze"
    else:
        if phase == "filtered":
            set_run_phase(conn2, run_id, "scraped")
        endpoint = f"{API_BASE}/api/pipeline/gathering/runs/{run_id}/analyze"
    conn2.close()

    try:
        requests.post(
            endpoint,
            params={"prompt_text": ICP_PROMPT, "model": "gpt-4o-mini"},
            headers=API_HEADERS,
            timeout=(5, 2),  # fire-and-forget
        )
    except requests.exceptions.ReadTimeout:
        pass  # expected — analysis runs in background
    except Exception as e:
        log.warning(f"  Analyze trigger error for run {run_id}: {e}")

    state["analyze_triggered"].append(run_id)
    save_progress(state)
    log.info(f"  ✓ Analyze triggered for run {run_id} ({RUNS[run_id]})")

# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    state = load_progress()
    done_ids = set(state["scraped_ids"] + state["failed_ids"])
    semaphore = asyncio.Semaphore(CONCURRENCY)

    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    run_ids = list(RUNS.keys())

    log.info(f"=== TFP Full Scrape started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")
    log.info(f"Already done: {len(done_ids)} companies")

    # Get ALL companies needing scrape
    companies = get_companies_needing_scrape(conn, run_ids)
    # Filter out already processed
    todo = [c for c in companies if c["id"] not in done_ids]
    log.info(f"Total to scrape: {len(todo)} companies (skipping {len(done_ids)} already done)")

    # Group by run for progress reporting
    by_run = {}
    for c in todo:
        by_run.setdefault(c["run_id"], []).append(c)
    for rid, items in sorted(by_run.items()):
        log.info(f"  Run {rid} ({RUNS[rid]}): {len(items)} to scrape")

    processed = 0
    batch_since_save = 0
    conn2 = psycopg2.connect(DB_URL)  # separate conn for writes (no cursor_factory needed)

    async def process_one(company):
        nonlocal processed, batch_since_save
        dc_id = company["id"]
        domain = company["domain"]
        try:
            expire_old_scrape(conn2, dc_id)
            result = await fetch_url(domain, semaphore)
            save_scrape_result(
                conn2, dc_id, domain,
                result["text"], result["html"],
                result["status_code"], result["success"], result["error"]
            )
            if result["success"] and len(result.get("text", "")) >= MIN_TEXT_LEN:
                state["scraped_ids"].append(dc_id)
                status = f"OK ({len(result['text'])} chars)"
            else:
                state["failed_ids"].append(dc_id)
                status = f"FAIL ({result.get('error', 'empty')})"
        except Exception as e:
            state["failed_ids"].append(dc_id)
            status = f"ERROR ({str(e)[:80]})"
            log.warning(f"  process_one failed for {domain}: {e}")

        processed += 1
        batch_since_save += 1

        if batch_since_save >= SAVE_EVERY:
            save_progress(state)
            batch_since_save = 0
            log.info(f"  Progress saved — {processed}/{len(todo)} done, "
                     f"{len(state['scraped_ids'])} good, {len(state['failed_ids'])} failed")

        if processed % 50 == 0:
            log.info(f"  [{processed}/{len(todo)}] {domain} → {status}")

    # Process in batches of CONCURRENCY
    tasks = [process_one(c) for c in todo]
    # Run with semaphore (already handles concurrency)
    await asyncio.gather(*tasks)

    save_progress(state)
    log.info(f"\n=== Scraping complete ===")
    log.info(f"  Good scrapes: {len(state['scraped_ids'])}")
    log.info(f"  Failed: {len(state['failed_ids'])}")

    # ── Trigger analyze for each run ──────────────────────────────────────────
    log.info("\n=== Triggering analysis for all runs ===")
    for run_id in run_ids:
        remaining = count_unscraped(conn, run_id)
        if remaining > 0:
            log.info(f"  Run {run_id} ({RUNS[run_id]}): {remaining} still have no text — analyzing anyway")
        trigger_analyze(run_id, state)
        await asyncio.sleep(3)  # stagger to avoid hammering API

    log.info("\n=== All done. Analysis running in background. ===")
    log.info("Monitor will pick up new targets and write to sheet automatically.")
    conn.close()
    conn2.close()


if __name__ == "__main__":
    asyncio.run(main())
