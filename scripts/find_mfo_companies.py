#!/usr/bin/env python3
"""
Find 50 multi-family office (MFO) companies in Russia.

Pipeline: Generate queries -> Yandex Search API -> Blacklist filter -> Scrape website -> GPT-4o-mini analysis
Reference ICP: https://oasiscapital.ru/ (multi-family office, wealth management, HNWI)

Runs until 50 VERIFIED target companies are gathered.
"""
import asyncio
import base64
import json
import os
import random
import re
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Set, List, Dict, Optional, Tuple
from urllib.parse import urlparse, quote_plus

import httpx
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mfo_search")

# ============================================================================
# CONFIG
# ============================================================================

# Load from backend .env
ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
env_vars = {}
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

YANDEX_API_KEY = env_vars.get("YANDEX_SEARCH_API_KEY", "")
YANDEX_FOLDER_ID = env_vars.get("YANDEX_SEARCH_FOLDER_ID", "")
YANDEX_SEARCH_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
YANDEX_OPS_URL = "https://operation.api.cloud.yandex.net/operations"
OPENAI_API_KEY = env_vars.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"

TARGET_COUNT = 50
MAX_YANDEX_PAGES = 3  # pages per query
SCRAPE_CONCURRENCY = 5
ANALYSIS_CONCURRENCY = 3

TARGET_SEGMENTS = (
    "Мульти фэмили офисы (Multi-family offices) в России и СНГ. "
    "Компании, управляющие активами состоятельных семей, "
    "инвестиционные компании для HNWI, wealth management фирмы, "
    "семейные офисы, управление семейным капиталом, private wealth."
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# ============================================================================
# BLACKLIST
# ============================================================================

def load_blacklist() -> Set[str]:
    bl_path = Path(__file__).parent.parent / "backend" / "app" / "services" / "blacklist_domains.txt"
    domains = set()
    if bl_path.exists():
        for line in bl_path.read_text().splitlines():
            d = line.strip().lower()
            if d:
                domains.add(d)
    log.info(f"Loaded {len(domains)} blacklist domains")
    return domains

BLACKLIST: Set[str] = set()  # loaded in main()

BASE_TRASH: Set[str] = {
    "ya.ru", "yandex.ru", "google.com", "avito.ru", "vk.com", "dzen.ru",
    "youtube.com", "prian.ru", "tranio.ru", "cian.ru", "rbc.ru", "wikipedia.org",
    "tinkoff.ru", "sberbank.ru", "domclick.ru", "hh.ru", "mvideo.ru",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "reddit.com", "pinterest.com", "tiktok.com", "ok.ru", "mail.ru", "t.me",
}

TRASH_PATTERNS: List[str] = [
    "t.me", "telegram", "vk.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com", "ok.ru",
    "linkedin.com", "pinterest.com", "reddit.com",
    "news.ru", "ria.ru", "lenta.ru", "rbc.ru", "kommersant", "forbes",
    "interfax", "tass.com", "rt.com", "gazeta", "vedomosti", "iz.ru",
    "banki.ru", "tbank.ru", "vtb.ru", "sberbank", "raiffeisen",
    "alfabank", "tinkoff", "gazprombank",
    "tranio.", "realting.com", "homesoverseas", "prian.", "cian.ru",
    "domclick", "avito.ru", "etagi.com",
    "booking.com", "agoda.com", "tripadvisor", "airbnb",
    "wikipedia.org", "wiki.", "yandex.ru", "google.com", "dzen.ru",
    "wise.com", "revolut.com", "stripe.com", "paypal",
    # Additional for MFO search - aggregators / irrelevant
    "habr.com", "vc.ru", "spark.ru", "rusprofile.ru", "list-org.com",
    "2gis.ru", "yell.ru", "zoon.ru", "cataloxy.ru", "yandex.com",
]


def normalize_domain(raw: str) -> str:
    d = raw.strip().lower()
    if not d:
        return ""
    if "://" in d:
        parsed = urlparse(d)
        d = parsed.hostname or d
    elif "/" in d:
        d = d.split("/")[0]
    d = d.rstrip(".")
    if d.startswith("www."):
        d = d[4:]
    return d


def is_trash(domain: str) -> bool:
    d = domain.lower()
    if d in BASE_TRASH or d in BLACKLIST:
        return True
    for pat in TRASH_PATTERNS:
        if pat in d:
            return True
    return False


# ============================================================================
# YANDEX SEARCH
# ============================================================================

async def yandex_search(query: str, max_pages: int = MAX_YANDEX_PAGES) -> Set[str]:
    """Search Yandex API (async/deferred mode) and return set of domains."""
    all_domains: Set[str] = set()
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }

    for page in range(max_pages):
        try:
            body = {
                "query": {
                    "searchType": "SEARCH_TYPE_RU",
                    "queryText": query,
                    "page": page,
                },
                "folderId": YANDEX_FOLDER_ID,
                "responseFormat": "FORMAT_HTML",
                "userAgent": random.choice(USER_AGENTS),
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(YANDEX_SEARCH_URL, json=body, headers=headers)

            if resp.status_code == 429:
                log.warning(f"  Yandex 429 for '{query}' page {page+1}, sleeping 5s...")
                await asyncio.sleep(5)
                continue

            if resp.status_code != 200:
                log.error(f"  Yandex {resp.status_code} for '{query}': {resp.text[:200]}")
                break

            op = resp.json()
            op_id = op.get("id")
            if not op_id:
                log.error(f"  No operation ID from Yandex for '{query}'")
                break

            # Poll until done
            html = await yandex_poll_operation(op_id, headers)
            if not html:
                log.warning(f"  Yandex poll timed out for '{query}' page {page+1}")
                break

            domains = extract_domains_from_html(html)
            new = domains - all_domains
            all_domains.update(domains)
            log.info(f"  Yandex '{query[:40]}...' page {page+1}: {len(new)} new, {len(all_domains)} total")

            if not new and page > 0:
                break

            # Small delay between pages
            if page < max_pages - 1:
                await asyncio.sleep(0.5)

        except Exception as e:
            log.error(f"  Yandex error for '{query}' page {page+1}: {e}")
            break

    return all_domains


async def yandex_poll_operation(op_id: str, headers: dict, max_wait: int = 60) -> Optional[str]:
    url = f"{YANDEX_OPS_URL}/{op_id}"
    for _ in range(max_wait):
        await asyncio.sleep(1.0)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not data.get("done"):
                continue
            raw_data = data.get("response", {}).get("rawData")
            if raw_data:
                return base64.b64decode(raw_data).decode("utf-8", errors="replace")
            return None
        except Exception:
            continue
    return None


def extract_domains_from_html(html: str) -> Set[str]:
    domains = set()
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: links
    for link in soup.find_all("a", href=True):
        href = link["href"]
        skip = ["google.com", "google.ru", "gstatic.com", "youtube.com",
                "webcache.", "/search?", "javascript:", "#", "yandex.ru", "yandex.com"]
        if any(x in href for x in skip):
            if "/url?q=" in href:
                match = re.search(r"/url\?q=([^&]+)", href)
                if match:
                    href = match.group(1)
                else:
                    continue
            else:
                continue
        try:
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                domain = normalize_domain(parsed.netloc)
                if domain and len(domain) > 3:
                    domains.add(domain)
        except Exception:
            continue

    # Method 2: cite elements
    for cite in soup.find_all("cite"):
        text = cite.get_text()
        match = re.search(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})", text)
        if match:
            domain = normalize_domain(match.group(1))
            if domain and len(domain) > 3:
                domains.add(domain)

    # Method 3: text URLs
    for text_url in re.findall(r'https?://([a-zA-Z0-9][-a-zA-Z0-9.]*\.[a-zA-Z]{2,})', html):
        domain = normalize_domain(text_url)
        if domain and len(domain) > 3:
            domains.add(domain)

    return domains


# ============================================================================
# WEBSITE SCRAPING
# ============================================================================

async def scrape_website(domain: str) -> Optional[str]:
    """Scrape website HTML. Try HTTPS then HTTP."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    for scheme in ["https", "http"]:
        url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                verify=False,
            ) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.text[:50000]
        except Exception:
            continue
    return None


# ============================================================================
# GPT ANALYSIS
# ============================================================================

async def analyze_company(domain: str, html: str, client: httpx.AsyncClient) -> Dict:
    """GPT-4o-mini analyzes if website matches MFO ICP."""
    html_excerpt = html[:8000] if html else ""

    prompt = f"""Проанализируй сайт и определи, является ли эта компания мульти-фэмили офисом / family office / управляющей компанией для состоятельных семей в России или СНГ.

ЦЕЛЕВОЙ СЕГМЕНТ: {TARGET_SEGMENTS}

РЕФЕРЕНС: Компании вроде Oasis Capital (oasiscapital.ru) — multi-family office, управление активами состоятельных семей, wealth management, инвестиционные решения для HNWI.

ДОМЕН: {domain}

HTML САЙТА (фрагмент):
{html_excerpt}

Ответь строго в JSON формате:
{{
  "is_target": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "краткое объяснение на русском",
  "company_info": {{
    "name": "название компании",
    "description": "краткое описание чем занимается",
    "services": ["список", "услуг"],
    "location": "город/регион",
    "industry": "отрасль"
  }}
}}

ВАЖНО:
- is_target=true ТОЛЬКО если компания реально управляет активами семей/HNWI или является family office
- Инвестиционные фонды, управляющие компании, private banking — тоже target если работают с HNWI/семьями
- Агрегаторы, новостные сайты, блоги, образовательные ресурсы — НЕ target
- Банки (Сбер, ВТБ и т.д.) — НЕ target, но бутиковый private banking — target
- confidence 0.8+ для явных совпадений
- Отвечай ТОЛЬКО валидным JSON"""

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert at analyzing Russian company websites. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 429:
                wait = (2 ** attempt) * 5 + random.uniform(0, 2)
                log.warning(f"  OpenAI 429 for {domain}, retry in {wait:.0f}s...")
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)

            # Parse JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    result = json.loads(content[start:end + 1])
                else:
                    result = {"is_target": False, "confidence": 0, "reasoning": "JSON parse error", "company_info": {}}

            result["tokens_used"] = tokens
            return result

        except Exception as e:
            if attempt == 2:
                return {"is_target": False, "confidence": 0, "reasoning": f"Error: {e}", "company_info": {}, "tokens_used": 0}
            await asyncio.sleep(2)

    return {"is_target": False, "confidence": 0, "reasoning": "Max retries", "company_info": {}, "tokens_used": 0}


# ============================================================================
# QUERY GENERATION
# ============================================================================

# Pre-built queries — regional + CEO phrasing + service variations
# Inspired by oasiscapital.ru reference

SEED_QUERIES = [
    # Direct MFO terms (Russian)
    "мульти фэмили офис Москва",
    "мульти фэмили офис Россия",
    "multi family office Москва",
    "multi family office Россия",
    "семейный офис управление активами",
    "семейный офис Москва",
    "семейный офис Санкт-Петербург",
    "family office Россия",
    "family office управление капиталом",
    "мультисемейный офис инвестиции",

    # Wealth management / HNWI
    "управление семейным капиталом Москва",
    "управление семейным капиталом Россия",
    "управление активами состоятельных семей",
    "управление благосостоянием HNWI Россия",
    "wealth management Россия",
    "wealth management Москва",
    "private wealth management Россия",
    "управление частным капиталом",
    "инвестиции для состоятельных семей",
    "управление крупным капиталом Россия",

    # Service variations (like oasiscapital.ru)
    "инвестиционный семейный офис",
    "инвестиционная компания для семей",
    "управляющая компания частный капитал",
    "доверительное управление активами семей",
    "стратегическое управление активами HNWI",
    "консалтинг для состоятельных семей",
    "финансовое планирование состоятельных семей",
    "структурирование семейного капитала",
    "семейный траст Россия",
    "наследственное планирование активов",

    # Regional — major Russian cities
    "family office Екатеринбург",
    "family office Новосибирск",
    "family office Казань",
    "управление капиталом Краснодар",
    "управление капиталом Сочи",
    "семейный офис Нижний Новгород",
    "private banking Самара",
    "wealth management Ростов-на-Дону",
    "семейный офис Уфа",
    "управление активами Тюмень",
    "семейный офис Воронеж",
    "управление капиталом Пермь",
    "управление активами Челябинск",

    # CEO / founder phrasing
    "основатель семейного офиса Россия",
    "генеральный директор family office",
    "управляющий партнер family office Москва",
    "CEO family office Russia",
    "основатель мульти фэмили офис",
    "руководитель управления активами HNWI",
    "партнер private wealth Россия",

    # Private banking (boutique)
    "бутиковый private banking Москва",
    "приватный банкинг для состоятельных семей",
    "бутик private banking Россия",
    "эксклюзивное управление активами",
    "VIP управление активами",
    "премиальное управление капиталом",

    # English queries
    "multi family office Russia",
    "family office Moscow Russia",
    "wealth management Russia HNWI",
    "private wealth Russia",
    "family office Saint Petersburg Russia",
    "asset management wealthy families Russia",
    "family office services Russia",
    "independent wealth management Russia",

    # Industry-adjacent
    "управление активами инвесторов Россия",
    "управление фондами частных клиентов",
    "инвестиционный бутик Россия",
    "независимый финансовый советник HNWI",
    "управление наследством капитал",
    "портфельное управление частные клиенты",
    "альтернативные инвестиции для семей",
    "фонд прямых инвестиций family",
]


async def generate_more_queries_gpt(existing: List[str], count: int = 30) -> List[str]:
    """Generate additional queries using GPT-4o-mini."""
    existing_sample = random.sample(existing, min(20, len(existing)))
    existing_str = "\n".join(f"  - {q}" for q in existing_sample)

    prompt = f"""Ты — эксперт по генерации поисковых запросов для поиска multi-family offices в России.

ЦЕЛЕВОЙ СЕГМЕНТ: {TARGET_SEGMENTS}
РЕФЕРЕНС: oasiscapital.ru — мульти фэмили офис, управление активами семей, wealth management.

УЖЕ ИСПОЛЬЗОВАННЫЕ ЗАПРОСЫ (НЕ ПОВТОРЯЙ!):
{existing_str}

Сгенерируй {count} НОВЫХ уникальных поисковых запросов.
Правила:
- 3-8 слов каждый
- 80% русский, 20% английский
- Комбинируй: тип компании + город/регион + услуга
- Используй CEO/founder phrasing: "основатель", "управляющий партнер", "руководитель"
- Города: Москва, СПб, Казань, Екатеринбург, Сочи, Краснодар, Владивосток и др.
- НЕ информационные запросы
- Ищем компании, а не статьи

Верни ТОЛЬКО JSON массив: ["запрос1", "запрос2", ...]"""

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "Generate search queries. Output ONLY valid JSON array."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.95,
        "max_tokens": 3000,
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code == 429:
                    wait = (2 ** attempt) * 5
                    log.warning(f"OpenAI 429 generating queries, retry in {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                # Parse
                try:
                    queries = json.loads(content)
                except json.JSONDecodeError:
                    start = content.find("[")
                    end = content.rfind("]")
                    if start != -1 and end != -1:
                        queries = json.loads(content[start:end+1])
                    else:
                        queries = []

                return [q.strip() for q in queries if q and len(q.strip()) > 5]

        except Exception as e:
            log.error(f"GPT query generation failed: {e}")
            if attempt == 2:
                return []
            await asyncio.sleep(3)

    return []


# ============================================================================
# MAIN PIPELINE
# ============================================================================

async def main():
    global BLACKLIST
    BLACKLIST = load_blacklist()

    log.info(f"=== MFO Company Search Pipeline ===")
    log.info(f"Target: {TARGET_COUNT} verified companies")
    log.info(f"Yandex API: {'configured' if YANDEX_API_KEY else 'MISSING'}")
    log.info(f"OpenAI API: {'configured' if OPENAI_API_KEY else 'MISSING'}")
    log.info(f"Blacklist: {len(BLACKLIST)} domains")

    if not YANDEX_API_KEY or not OPENAI_API_KEY:
        log.error("Missing API keys! Check backend/.env")
        return

    # Tracking
    all_queries_used: List[str] = []
    all_domains_seen: Set[str] = set()
    all_domains_scraped: Set[str] = set()
    target_companies: List[Dict] = []
    non_target_companies: List[Dict] = []
    total_yandex_queries = 0
    total_openai_tokens = 0
    start_time = time.time()

    # Results file
    results_path = Path(__file__).parent / "mfo_results.json"

    def save_results():
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "target_count": len(target_companies),
            "total_domains_seen": len(all_domains_seen),
            "total_domains_scraped": len(all_domains_scraped),
            "total_yandex_queries": total_yandex_queries,
            "total_openai_tokens": total_openai_tokens,
            "elapsed_seconds": round(time.time() - start_time, 1),
            "targets": target_companies,
            "non_targets": non_target_companies,
        }
        results_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # ==== ROUND 1: Seed queries ====
    queries_to_run = list(SEED_QUERIES)
    round_num = 0

    while len(target_companies) < TARGET_COUNT:
        round_num += 1
        log.info(f"\n{'='*60}")
        log.info(f"ROUND {round_num} | Targets so far: {len(target_companies)}/{TARGET_COUNT}")
        log.info(f"Queries this round: {len(queries_to_run)}")
        log.info(f"{'='*60}")

        if not queries_to_run:
            # Generate more queries
            log.info("Generating more queries with GPT...")
            new_queries = await generate_more_queries_gpt(all_queries_used, count=40)
            # Filter out already used
            used_norm = set(q.lower().strip() for q in all_queries_used)
            queries_to_run = [q for q in new_queries if q.lower().strip() not in used_norm]
            log.info(f"Generated {len(queries_to_run)} new queries")
            if not queries_to_run:
                log.warning("No more queries can be generated. Stopping.")
                break

        # Phase 1: Yandex search
        round_domains: Set[str] = set()
        for i, query in enumerate(queries_to_run):
            if len(target_companies) >= TARGET_COUNT:
                break

            log.info(f"\n[{i+1}/{len(queries_to_run)}] Searching: '{query}'")
            all_queries_used.append(query)
            total_yandex_queries += 1

            domains = await yandex_search(query, max_pages=MAX_YANDEX_PAGES)

            # Filter
            new_domains = set()
            trash_count = 0
            dup_count = 0
            for d in domains:
                d = normalize_domain(d)
                if not d or len(d) < 4:
                    continue
                if is_trash(d):
                    trash_count += 1
                    continue
                if d in all_domains_seen:
                    dup_count += 1
                    continue
                all_domains_seen.add(d)
                new_domains.add(d)

            round_domains.update(new_domains)
            log.info(f"  -> {len(new_domains)} new, {trash_count} trash, {dup_count} dup")

            # Small delay between queries
            await asyncio.sleep(0.3)

        log.info(f"\nRound {round_num} Yandex: {len(round_domains)} new domains to analyze")

        if not round_domains:
            log.info("No new domains found. Generating more queries...")
            queries_to_run = []
            continue

        # Phase 2: Scrape + analyze
        domains_list = list(round_domains)
        scrape_sem = asyncio.Semaphore(SCRAPE_CONCURRENCY)
        analysis_sem = asyncio.Semaphore(ANALYSIS_CONCURRENCY)

        openai_client = httpx.AsyncClient(timeout=60)

        async def process_domain(domain: str):
            nonlocal total_openai_tokens
            if domain in all_domains_scraped:
                return
            all_domains_scraped.add(domain)

            # Scrape
            async with scrape_sem:
                html = await scrape_website(domain)

            if not html:
                log.info(f"  SKIP {domain} (scrape failed)")
                return

            if len(html.strip()) < 200:
                log.info(f"  SKIP {domain} (too short: {len(html)} chars)")
                return

            # Analyze
            async with analysis_sem:
                result = await analyze_company(domain, html, openai_client)

            total_openai_tokens += result.get("tokens_used", 0)

            if result.get("is_target") and result.get("confidence", 0) >= 0.7:
                company_info = result.get("company_info", {})
                entry = {
                    "domain": domain,
                    "name": company_info.get("name", ""),
                    "description": company_info.get("description", ""),
                    "services": company_info.get("services", []),
                    "location": company_info.get("location", ""),
                    "industry": company_info.get("industry", ""),
                    "confidence": result.get("confidence", 0),
                    "reasoning": result.get("reasoning", ""),
                }
                target_companies.append(entry)
                n = len(target_companies)
                log.info(f"  TARGET #{n} {domain} — {company_info.get('name', '?')} (conf={result['confidence']:.2f})")
            else:
                non_target_companies.append({
                    "domain": domain,
                    "confidence": result.get("confidence", 0),
                    "reasoning": result.get("reasoning", ""),
                })
                log.info(f"  NOT TARGET {domain} (conf={result.get('confidence', 0):.2f}) — {result.get('reasoning', '')[:80]}")

        # Process in batches
        batch_size = 15
        for batch_start in range(0, len(domains_list), batch_size):
            if len(target_companies) >= TARGET_COUNT:
                break

            batch = domains_list[batch_start:batch_start + batch_size]
            log.info(f"\nProcessing batch {batch_start//batch_size + 1} ({len(batch)} domains)...")
            await asyncio.gather(*[process_domain(d) for d in batch], return_exceptions=True)

            # Save intermediate results
            save_results()

            log.info(f"  Progress: {len(target_companies)}/{TARGET_COUNT} targets | "
                     f"{len(all_domains_scraped)} scraped | "
                     f"{total_yandex_queries} Yandex queries | "
                     f"{total_openai_tokens} OpenAI tokens")

        await openai_client.aclose()

        # Prepare next round
        queries_to_run = []  # Will trigger GPT generation in next iteration

    # Final save
    save_results()

    elapsed = time.time() - start_time
    log.info(f"\n{'='*60}")
    log.info(f"PIPELINE COMPLETE")
    log.info(f"{'='*60}")
    log.info(f"Targets found: {len(target_companies)}/{TARGET_COUNT}")
    log.info(f"Total domains seen: {len(all_domains_seen)}")
    log.info(f"Total domains scraped: {len(all_domains_scraped)}")
    log.info(f"Yandex queries: {total_yandex_queries}")
    log.info(f"OpenAI tokens: {total_openai_tokens}")
    log.info(f"Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    log.info(f"Results saved to: {results_path}")

    # Print targets
    log.info(f"\n=== VERIFIED TARGET COMPANIES ({len(target_companies)}) ===")
    for i, t in enumerate(target_companies, 1):
        log.info(f"  {i:2d}. {t['domain']:30s} | {t['name']:30s} | {t['location']:15s} | conf={t['confidence']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
