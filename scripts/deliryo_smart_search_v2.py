#!/usr/bin/env python3
"""
Deliryo Smart Search v2 — Persistent, self-improving search engine.

Runs continuously until TARGET_GOAL reached. Iterates through multiple
strategy rounds. All decisions and results stored in DB for analysis.

Architecture:
- Round 1-12: Hand-crafted strategy rounds (12 diverse strategies)
- Round 13+: GPT generates new queries based on WHAT ACTUALLY WORKED
  (confirmed target domains, their industries, query patterns)
- Each round: generate queries → search → scrape → analyze → review → learn
- Strategy tracking: which query patterns produce targets, which don't
- Stops when target reached or all strategies exhausted

Reusable Pattern — "Query Anchors":
  For ANY geo, the approach is: list ALL regions/cities first ("anchors"),
  then multiply × industry terms. This works for Russia, UAE, DACH, etc.
  Russia: 85 federal subjects + 100+ cities × 8 industry terms
  UAE:    7 emirates + districts × terms
  DACH:   16+26+9 cantons/Länder + cities × terms
"""
import asyncio
import sys
import os
import logging
import signal
import random
import json
from datetime import datetime
from itertools import product

_script_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.join(_script_dir, '..', 'backend')
if os.path.isdir(_backend_dir):
    sys.path.insert(0, _backend_dir)
elif os.path.isdir('/app'):
    sys.path.insert(0, '/app')

from app.db import async_session_maker, engine
from app.core.config import settings
from app.models.contact import Project
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchResult, ProjectSearchKnowledge,
)
from app.services.search_service import search_service
from app.services.company_search_service import company_search_service
from sqlalchemy import select, func, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger("smart2")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

PROJECT_ID = 18
COMPANY_ID = 1
TARGET_GOAL = 1000
YANDEX_WORKERS = 8
CRONA_BATCH_SIZE = 60
CRONA_PARALLEL = 5
GPT_CONCURRENT = 40
BATCH_SIZE = 25  # queries per batch

shutdown_requested = False

def handle_signal(signum, frame):
    global shutdown_requested
    logger.warning("Shutdown requested...")
    shutdown_requested = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


# ═══════════════════════════════════════════════════════════════════════
# QUERY GENERATION — 12 STRATEGIES
# ═══════════════════════════════════════════════════════════════════════

def strategy_core_combos():
    """Core industry terms × modifiers — the bread and butter."""
    queries = set()
    terms = [
        "управляющая компания", "управление активами",
        "инвестиционная компания", "инвестиционный фонд",
        "wealth management", "private banking",
        "доверительное управление", "фэмили офис",
        "фэмили офис", "брокерская компания",
        "финансовый консультант", "инвестиционный консалтинг",
        "независимый финансовый советник",
        "персональный финансовый консультант",
        "трастовая компания", "управление капиталом",
        "инвестиционный советник",
    ]
    mods = [
        "реестр", "список", "рейтинг", "топ", "лицензия ЦБ",
        "каталог", "для состоятельных клиентов", "для HNWI",
        "премиум", "Россия", "обзор", "сравнение",
    ]
    for t, m in product(terms, mods):
        queries.add(f"{t} {m}")
    return "core_combos", list(queries)


def strategy_regulatory():
    """Regulatory registries and directories."""
    return "regulatory", [
        "реестр управляющих компаний Банк России",
        "ЦБ РФ реестр участников финансового рынка",
        "НАУФОР реестр членов",
        "НАУФОР управляющие компании список",
        "НФА национальная финансовая ассоциация",
        "Investfunds рейтинг управляющих компаний",
        "RAEX рейтинг управляющих компаний",
        "Эксперт РА рейтинг управляющих",
        "АКРА рейтинг финансовых компаний",
        "НРА рейтинг управляющих",
        "cbr.ru реестр лицензий управляющих",
        "investfunds.ru управляющие компании",
        "moex.com участники торгов",
        "спарк управляющая компания инвестиции",
        "реестр инвестиционных советников ЦБ",
        "единый реестр участников финансового рынка",
        "реестр ПИФ Банк России",
        "реестр НПФ Банк России",
        "реестр брокеров ЦБ РФ",
        "реестр дилеров ЦБ РФ",
    ]


def strategy_fund_types():
    """Specific fund and company types from CBR classifications."""
    return "fund_types", [
        "паевой инвестиционный фонд ПИФ",
        "закрытый паевой инвестиционный фонд",
        "ЗПИФ недвижимости", "ЗПИФ венчурный",
        "ЗПИФ рентный", "ЗПИФ кредитный",
        "открытый паевой инвестиционный фонд",
        "интервальный паевой инвестиционный фонд",
        "биржевой паевой инвестиционный фонд",
        "негосударственный пенсионный фонд НПФ",
        "НПФ управление пенсионными накоплениями",
        "инвестиционный советник реестр",
        "специализированный депозитарий",
        "управляющая компания ПИФ",
        "управляющая компания НПФ",
        "инвестиционная платформа Россия",
        "краудинвестинг платформа Россия",
        "краудлендинг Россия",
    ]


def strategy_legal_tax():
    """Legal and tax services for wealthy clients."""
    return "legal_tax", [
        "юридические услуги для состоятельных клиентов",
        "налоговое планирование крупный капитал",
        "структурирование активов юридическая фирма",
        "защита активов юристы Россия",
        "наследственное планирование юристы",
        "создание личного фонда Россия",
        "трастовые услуги Россия",
        "КИК консалтинг юристы",
        "деофшоризация юридические услуги",
        "международное налоговое планирование",
        "due diligence инвестиции юристы",
        "M&A юридические услуги Россия",
        "корпоративное право инвестиции",
        "правовое сопровождение инвестиций",
        "юрист для HNWI",
        "адвокат для бизнеса инвестиции",
        "семейное право состоятельные клиенты",
        "имущественное планирование юристы",
        "бутиковая юридическая фирма Москва",
        "юридический консалтинг финансы",
    ]


def strategy_crypto():
    """Crypto and digital assets."""
    return "crypto", [
        "обмен USDT рубли юридические лица",
        "OTC криптовалюта обмен Россия",
        "крипто брокер Россия",
        "крипто custody Россия",
        "криптовалютный консалтинг",
        "легальный обмен криптовалют Россия",
        "цифровые активы управление",
        "digital assets management Russia",
        "блокчейн инвестиции фонд",
        "токенизация активов",
        "крипто фонд Россия",
        "майнинг инвестиции Россия",
    ]


def strategy_russia_regions():
    """All Russian cities pop>250K + ALL 85 federal subjects + economic zones."""
    queries = set()
    terms = [
        "управление активами", "инвестиционная компания",
        "wealth management", "фэмили офис",
        "доверительное управление", "private banking",
        "управляющая компания", "инвестиционный фонд",
    ]
    # ── Russian cities pop > 200K (comprehensive) ──
    cities = [
        # 1M+
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
        "Казань", "Нижний Новгород", "Челябинск", "Самара",
        "Омск", "Ростов-на-Дону", "Уфа", "Красноярск",
        "Воронеж", "Пермь", "Волгоград", "Краснодар",
        # 500K-1M
        "Саратов", "Тюмень", "Барнаул", "Иркутск",
        "Хабаровск", "Ярославль", "Владивосток", "Махачкала",
        "Томск", "Оренбург", "Кемерово", "Рязань",
        "Набережные Челны", "Астрахань", "Пенза", "Киров",
        "Липецк", "Калининград", "Тула", "Курск",
        # 300K-500K
        "Ставрополь", "Сочи", "Улан-Удэ", "Тверь",
        "Магнитогорск", "Брянск", "Иваново", "Белгород",
        "Сургут", "Владимир", "Архангельск", "Чита",
        "Калуга", "Смоленск", "Курган", "Череповец",
        "Вологда", "Якутск", "Мурманск", "Тамбов",
        "Грозный", "Петрозаводск", "Кострома",
        "Новороссийск", "Сыктывкар", "Нальчик",
        # 200K-300K
        "Чебоксары", "Ижевск", "Ульяновск", "Тольятти",
        "Балашиха", "Нижний Тагил", "Нижневартовск",
        "Йошкар-Ола", "Комсомольск-на-Амуре", "Таганрог",
        "Дзержинск", "Братск", "Шахты", "Нижнекамск",
        "Орск", "Ангарск", "Саранск", "Орёл",
        "Стерлитамак", "Волжский", "Южно-Сахалинск",
        "Благовещенск", "Абакан", "Великий Новгород",
        "Псков", "Бийск", "Рыбинск", "Прокопьевск",
        "Норильск", "Балаково", "Энгельс", "Сызрань",
        "Каменск-Уральский", "Армавир", "Златоуст",
        "Салават", "Миасс", "Копейск", "Королёв",
        "Мытищи", "Химки", "Подольск", "Одинцово",
        "Люберцы", "Красногорск",
    ]
    # ── ALL 85 Russian federal subjects ──
    regions = [
        # Republics (22)
        "Адыгея", "Алтай", "Башкортостан", "Бурятия", "Дагестан",
        "Ингушетия", "Кабардино-Балкария", "Калмыкия", "Карачаево-Черкесия",
        "Карелия", "Коми", "Крым", "Марий Эл", "Мордовия",
        "Саха Якутия", "Северная Осетия", "Татарстан", "Тува",
        "Удмуртия", "Хакасия", "Чечня", "Чувашия",
        # Krais (9)
        "Алтайский край", "Забайкальский край", "Камчатский край",
        "Краснодарский край", "Красноярский край", "Пермский край",
        "Приморский край", "Ставропольский край", "Хабаровский край",
        # Oblasts (46)
        "Амурская область", "Архангельская область", "Астраханская область",
        "Белгородская область", "Брянская область", "Владимирская область",
        "Волгоградская область", "Вологодская область", "Воронежская область",
        "Ивановская область", "Иркутская область", "Калининградская область",
        "Калужская область", "Кемеровская область", "Кировская область",
        "Костромская область", "Курганская область", "Курская область",
        "Ленинградская область", "Липецкая область", "Магаданская область",
        "Московская область", "Мурманская область", "Нижегородская область",
        "Новгородская область", "Новосибирская область", "Омская область",
        "Оренбургская область", "Орловская область", "Пензенская область",
        "Псковская область", "Ростовская область", "Рязанская область",
        "Самарская область", "Саратовская область", "Сахалинская область",
        "Свердловская область", "Смоленская область", "Тамбовская область",
        "Тверская область", "Томская область", "Тульская область",
        "Тюменская область", "Ульяновская область", "Челябинская область",
        "Ярославская область",
        # Autonomous & special
        "ХМАО", "ЯНАО", "ЕАО", "Ненецкий АО", "Чукотский АО",
        "Севастополь",
    ]
    # ── Economic zones / wealth clusters (high-priority anchors) ──
    wealth_anchors = [
        "Рублёвка", "Жуковка", "Барвиха",  # Moscow suburbs = HNWI density
        "ОЭЗ", "Сколково", "Иннополис",     # economic zones
        "Москва-Сити",                        # financial district
    ]
    for t, city in product(terms, cities):
        queries.add(f"{t} {city}")
    for t, region in product(terms[:4], regions):
        queries.add(f"{t} {region}")
    for t, wa in product(terms[:4], wealth_anchors):
        queries.add(f"{t} {wa}")
    return "russia_regions", list(queries)


def strategy_events_media():
    """Conferences, awards, media mentions."""
    return "events_media", [
        "конференция private banking Россия",
        "конференция управление активами",
        "форум wealth management Россия",
        "SPEAR'S Russia wealth management",
        "Forbes Club инвестиции",
        "РБК конференция инвестиции",
        "Ведомости конференция управление капиталом",
        "Private Banking Awards Russia",
        "EMEA Finance Awards Russia",
        "рейтинг wealth management Forbes",
        "рейтинг инвестиционных компаний РБК",
        "лучшие управляющие компании 2024",
        "лучшие инвестиционные консультанты Россия",
        "премия управление активами",
        "Банковское обозрение private banking",
        "Frank RG wealth management",
        "Bloomchain инвестиции",
        "vc.ru инвестиционные компании",
    ]


def strategy_real_estate():
    """Real estate investment management."""
    return "real_estate", [
        "управление коммерческой недвижимостью инвестиции",
        "инвестиции в недвижимость управляющая компания",
        "фонд недвижимости Россия",
        "закрытый фонд недвижимости",
        "управление портфелем недвижимости",
        "арендный бизнес управление",
        "коллективные инвестиции недвижимость",
        "девелопер инвестиционный фонд",
        "REIT Россия аналог",
        "инвестиции в складскую недвижимость",
    ]


def strategy_alternative():
    """Alternative investments — VC, PE, hedge, art."""
    return "alternative", [
        "венчурный фонд Россия",
        "venture capital Russia",
        "private equity фонд Россия",
        "фонд прямых инвестиций Россия",
        "хедж фонд Россия",
        "hedge fund Russia",
        "art banking инвестиции",
        "инвестиции в искусство",
        "мезонинное финансирование",
        "structured products Россия",
        "структурные продукты инвестиции",
        "commodity fund Russia",
        "фонд товарного рынка",
        "клуб инвесторов Россия",
        "бизнес ангел сообщество Россия",
        "синдикат инвесторов",
    ]


def strategy_insurance_pension():
    """Insurance and pension products."""
    return "insurance", [
        "инвестиционное страхование жизни",
        "накопительное страхование жизни",
        "ИСЖ компании Россия",
        "НСЖ для состоятельных клиентов",
        "unit-linked страхование",
        "страхование жизни HNWI",
        "пенсионное планирование состоятельных",
        "корпоративное пенсионное обеспечение",
    ]


def strategy_domain_tld():
    """Domain pattern and TLD searches."""
    return "domain_tld", [
        "site:*.capital", "site:*.fund", "site:*.finance",
        "site:*.investments", "site:*.partners инвестиции",
        "site:*.pro инвестиции", "site:*.legal финансовое право",
        "site:*.ru инвестиционная компания",
        "site:*-am.ru", "site:*-capital.ru",
        "site:*invest.ru", "site:*trust.ru",
        "site:*wealth.ru", "site:*broker.ru",
        "site:*fond.ru", "site:*asset.ru",
    ]


def strategy_english():
    """English queries for international-facing Russian firms."""
    return "english", [
        "wealth management companies Russia",
        "asset management firms Russia",
        "investment advisory Russia",
        "family office Russia",
        "trust company Russia",
        "private equity Russia",
        "venture capital Russia",
        "financial advisory HNWI Russia",
        "independent financial advisor Russia",
        "fiduciary services Russia",
        "portfolio management Russia",
        "discretionary management Russia",
        "investment boutique Russia",
        "multi-family office Russia",
        "wealth planning Russia",
        "estate planning Russia",
        "tax advisory wealthy Russia",
        "asset protection Russia",
        "investment management firm Russia list",
        "top investment companies Russia",
        "best wealth managers Russia",
        "Russia top investment firms",
        "Russian investment companies list",
        "Russian asset management firms",
    ]


ALL_STRATEGIES = [
    strategy_core_combos,
    strategy_regulatory,
    strategy_fund_types,
    strategy_legal_tax,
    strategy_crypto,
    strategy_russia_regions,
    strategy_events_media,
    strategy_real_estate,
    strategy_alternative,
    strategy_insurance_pension,
    strategy_domain_tld,
    strategy_english,
]


async def generate_gpt_queries(session, round_num, target_segments, confirmed_targets):
    """GPT generates fresh queries based on what worked."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    target_examples = "\n".join(f"- {d}" for d in confirmed_targets[:50])

    prompt = f"""You are generating Yandex search queries to find companies similar to these confirmed targets.

Target description: {target_segments[:500]}

Examples of confirmed target domains (these are wealth management, investment, legal firms):
{target_examples}

Generate 100 DIVERSE Yandex search queries. Requirements:
1. RUSSIA ONLY — no CIS, no international. All targets must be Russian companies
2. DO NOT repeat the same pattern with different cities — geo-specific queries are exhausted
3. Focus on INDUSTRY TERMS, REGULATORY DATABASES, PROFESSIONAL DIRECTORIES
4. Include niche subsectors: private equity, venture capital, hedge funds, structured products
5. Include adjacent services: legal for wealthy, tax planning, trust management
6. Try NOVEL angles: company registries, professional associations, industry catalogs
7. Mix Russian and English queries (English queries should include "Russia" or "Russian")
8. Try specific company characteristics: "лицензия ЦБ 045", "НАУФОР член", etc.
9. Use "фэмили офис" (NOT "семейный офис") — that's how Russians say it

This is round {round_num}. Previous rounds already tried standard wealth management queries.
Think of what HASN'T been searched yet.

Return ONLY the queries, one per line, no numbering."""

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=4000,
        )
        text = resp.choices[0].message.content
        queries = [q.strip().lstrip("- ").lstrip("0123456789.").strip()
                    for q in text.strip().split("\n") if q.strip()]
        logger.info(f"  GPT generated {len(queries)} queries for round {round_num}")
        return "gpt_round_" + str(round_num), queries
    except Exception as e:
        logger.error(f"  GPT query gen failed: {e}")
        return "gpt_round_" + str(round_num), []


# ═══════════════════════════════════════════════════════════════════════
# MONKEY-PATCH CONCURRENCY
# ═══════════════════════════════════════════════════════════════════════

def patch_concurrency():
    import app.services.company_search_service as css_mod

    async def patched(self, session, job, domains, target_segments):
        import asyncio as aio
        from app.services.crona_service import crona_service

        total_tokens = (job.config or {}).get("openai_tokens_used", 0)
        crona_credits = 0

        existing = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == job.project_id,
                SearchResult.domain.in_(domains)))
        existing_set = {r[0] for r in existing.fetchall()}
        to_analyze = [d for d in domains if d not in existing_set]
        if not to_analyze:
            return

        scraped = {}
        used_crona = False
        if crona_service.is_configured:
            sem = aio.Semaphore(CRONA_PARALLEL)
            async def scrape_batch(b):
                async with sem:
                    return await crona_service.scrape_domains(b)
            batches = [to_analyze[i:i+CRONA_BATCH_SIZE] for i in range(0, len(to_analyze), CRONA_BATCH_SIZE)]
            results = await aio.gather(*[scrape_batch(b) for b in batches], return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    scraped.update(r)
            crona_credits = crona_service.credits_used
            used_crona = True
        else:
            sem = aio.Semaphore(10)
            async def s(d):
                async with sem:
                    scraped[d] = await self.scrape_domain(d)
            await aio.gather(*[s(d) for d in to_analyze], return_exceptions=True)

        scraped_at = datetime.utcnow()
        dq = (job.config or {}).get("domain_to_query", {})
        sem = aio.Semaphore(GPT_CONCURRENT)

        async def analyze(domain):
            nonlocal total_tokens
            async with sem:
                content = scraped.get(domain)
                sqid = dq.get(domain)
                if not content or len(content) < 50:
                    session.add(SearchResult(
                        search_job_id=job.id, project_id=job.project_id,
                        domain=domain, url=f"https://{domain}",
                        is_target=False, confidence=0, reasoning="No content",
                        scraped_at=scraped_at, source_query_id=sqid))
                    return
                a = await self.analyze_company(content, target_segments, domain, is_html=not used_crona)
                total_tokens += a.get("tokens_used", 0)
                session.add(SearchResult(
                    search_job_id=job.id, project_id=job.project_id,
                    domain=domain, url=f"https://{domain}",
                    is_target=a.get("is_target", False), confidence=a.get("confidence", 0),
                    reasoning=a.get("reasoning", ""), company_info=a.get("company_info", {}),
                    scores=a.get("scores", {}), html_snippet=content[:2000],
                    scraped_at=scraped_at, analyzed_at=datetime.utcnow(), source_query_id=sqid))

        for i in range(0, len(to_analyze), GPT_CONCURRENT):
            batch = to_analyze[i:i+GPT_CONCURRENT]
            await aio.gather(*[analyze(d) for d in batch], return_exceptions=True)
            await session.flush()

        cfg = dict(job.config or {})
        cfg["openai_tokens_used"] = total_tokens
        cfg["crona_credits_used"] = cfg.get("crona_credits_used", 0) + crona_credits
        job.config = cfg

    css_mod.CompanySearchService._scrape_and_analyze_domains = patched
    settings.SEARCH_WORKERS = YANDEX_WORKERS


# ═══════════════════════════════════════════════════════════════════════
# MAIN LOOP — RUNS UNTIL TARGET_GOAL OR ALL STRATEGIES EXHAUSTED
# ═══════════════════════════════════════════════════════════════════════

async def run_round(session, project, job, queries, strategy_name, round_num, start_targets):
    """Run one round of queries. Returns (targets_gained, domains_analyzed)."""
    round_start = datetime.utcnow()
    existing = await company_search_service._count_project_targets(session, PROJECT_ID)
    round_start_targets = existing
    total_analyzed = 0

    logger.info(f"\n{'='*60}")
    logger.info(f"ROUND {round_num}: strategy={strategy_name} | {len(queries)} queries | targets={existing}/{TARGET_GOAL}")
    logger.info(f"{'='*60}")

    for i in range(0, len(queries), BATCH_SIZE):
        if shutdown_requested or existing >= TARGET_GOAL:
            break

        batch = queries[i:i + BATCH_SIZE]
        elapsed = (datetime.utcnow() - round_start).total_seconds()
        gained_total = existing - start_targets
        gained_round = existing - round_start_targets

        logger.info(f"\n  [B{i//BATCH_SIZE+1}] q={i+1}-{i+len(batch)}/{len(queries)} | "
                     f"round:+{gained_round} total:+{gained_total} ({existing}/{TARGET_GOAL}) | "
                     f"{elapsed/60:.0f}min")

        for q in batch:
            session.add(SearchQuery(search_job_id=job.id, query_text=q))
        job.queries_total = (job.queries_total or 0) + len(batch)
        await session.commit()

        t0 = datetime.utcnow()
        await search_service.run_search_job(session, job.id)
        await session.refresh(job)
        yt = (datetime.utcnow() - t0).total_seconds()

        skip = await company_search_service._build_skip_set(session, PROJECT_ID)
        new_d = await company_search_service._get_new_domains_from_job(session, job, skip)

        logger.info(f"    yandex={yt:.0f}s new={len(new_d)} skip={len(skip)}")

        if new_d:
            total_analyzed += len(new_d)
            await company_search_service._scrape_and_analyze_domains(
                session=session, job=job, domains=new_d,
                target_segments=project.target_segments)
            await session.commit()

            try:
                from app.services.review_service import review_service
                await review_service.review_batch(session, job.id, project.target_segments)
                await session.commit()
            except Exception:
                pass

        new_existing = await company_search_service._count_project_targets(session, PROJECT_ID)
        delta = new_existing - existing
        existing = new_existing
        if delta > 0:
            logger.info(f"    >>> +{delta} TARGETS ({strategy_name}) | total={existing} <<<")

    gained = existing - round_start_targets
    rt = (datetime.utcnow() - round_start).total_seconds()
    logger.info(f"\n  Round {round_num} done: +{gained} targets, {total_analyzed} analyzed, {rt/60:.1f}min")
    return gained, total_analyzed


async def run():
    patch_concurrency()

    async with async_session_maker() as session:
        project = (await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )).scalar_one_or_none()
        if not project:
            logger.error("Project not found!")
            return

        existing = await company_search_service._count_project_targets(session, PROJECT_ID)
        global_start = existing
        logger.info(f"Project: {project.name} | Targets: {existing}/{TARGET_GOAL}")

        if existing >= TARGET_GOAL:
            logger.info("Already done!")
            return

        job = SearchJob(
            company_id=COMPANY_ID, status=SearchJobStatus.RUNNING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=0, project_id=PROJECT_ID,
            started_at=datetime.utcnow(),
            config={"smart_v2": True, "start_targets": existing},
        )
        session.add(job)
        await session.commit()
        logger.info(f"Job #{job.id}")

        run_start = datetime.utcnow()
        round_num = 0
        strategy_stats = {}  # strategy_name -> {queries, targets, domains}

        # Phase 1: Run all hand-crafted strategies
        for strategy_fn in ALL_STRATEGIES:
            if shutdown_requested or existing >= TARGET_GOAL:
                break

            name, queries = strategy_fn()
            random.shuffle(queries)
            round_num += 1

            gained, analyzed = await run_round(
                session, project, job, queries, name, round_num, global_start)

            strategy_stats[name] = {
                "queries": len(queries), "targets": gained, "domains": analyzed}

            existing = await company_search_service._count_project_targets(session, PROJECT_ID)

            # Persist stats to DB after every strategy (survives crashes)
            cfg = dict(job.config or {})
            cfg["strategy_stats"] = strategy_stats
            cfg["current_round"] = round_num
            cfg["current_targets"] = existing
            job.config = cfg
            await session.commit()

            # Log strategy leaderboard
            logger.info(f"\n  Strategy leaderboard:")
            for sn, ss in sorted(strategy_stats.items(), key=lambda x: -x[1]["targets"]):
                eff = ss["targets"] / max(ss["queries"], 1) * 100
                logger.info(f"    {sn}: +{ss['targets']} targets from {ss['queries']}q ({eff:.1f}% eff)")

        # Phase 2: GPT-generated rounds until goal reached
        gpt_round = 0
        MAX_GPT_ROUNDS = 50  # safety limit
        consecutive_zero = 0

        while not shutdown_requested and existing < TARGET_GOAL and gpt_round < MAX_GPT_ROUNDS:
            gpt_round += 1
            round_num += 1

            # Get confirmed targets for GPT context
            confirmed = await session.execute(
                select(SearchResult.domain).where(
                    SearchResult.project_id == PROJECT_ID,
                    SearchResult.is_target == True,
                    SearchResult.review_status != "rejected",
                ).limit(100)
            )
            confirmed_domains = [r[0] for r in confirmed.fetchall()]

            name, queries = await generate_gpt_queries(
                session, gpt_round, project.target_segments, confirmed_domains)

            if not queries:
                logger.warning("GPT returned no queries, stopping")
                break

            gained, analyzed = await run_round(
                session, project, job, queries, name, round_num, global_start)

            strategy_stats[name] = {
                "queries": len(queries), "targets": gained, "domains": analyzed}

            existing = await company_search_service._count_project_targets(session, PROJECT_ID)

            if gained == 0:
                consecutive_zero += 1
                if consecutive_zero >= 5:
                    logger.warning(f"5 consecutive rounds with 0 targets, stopping")
                    break
            else:
                consecutive_zero = 0

        # Done
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        total_time = (datetime.utcnow() - run_start).total_seconds()
        total_gained = existing - global_start

        cfg = dict(job.config or {})
        cfg["final_targets"] = existing
        cfg["gained"] = total_gained
        cfg["rounds"] = round_num
        cfg["strategy_stats"] = strategy_stats
        cfg["total_time_min"] = total_time / 60
        job.config = cfg
        await session.commit()

        logger.info(f"\n{'='*60}")
        logger.info(f"SMART SEARCH v2 COMPLETE")
        logger.info(f"  Targets: {global_start} → {existing} (+{total_gained})")
        logger.info(f"  Rounds: {round_num}")
        logger.info(f"  Time: {total_time/60:.0f}min")
        logger.info(f"  Rate: {total_gained/max(total_time/60,0.01):.2f}/min")
        logger.info(f"\n  Strategy leaderboard (final):")
        for sn, ss in sorted(strategy_stats.items(), key=lambda x: -x[1]["targets"]):
            eff = ss["targets"] / max(ss["queries"], 1) * 100
            logger.info(f"    {sn}: +{ss['targets']} targets, {ss['queries']}q, {ss['domains']}d ({eff:.1f}%)")
        logger.info(f"{'='*60}")


async def main():
    try:
        await run()
    except Exception as e:
        logger.error(f"Crashed: {e}", exc_info=True)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
