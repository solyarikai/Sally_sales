#!/usr/bin/env python3
"""
Deliryo Smart Search — Diverse query strategies based on target analysis.

Instead of GPT-generated geo-specific queries that saturate quickly,
uses multiple search angles:
1. Domain name patterns (capital, invest, trust, am, wealth, fund)
2. Industry-specific Russian terms (доверительное управление, УК)
3. Regulatory/directory searches (ЦБ реестр, рейтинги)
4. Conference/event attendees
5. Related service providers (legal, tax for HNWI)
6. CIS countries (Kazakhstan, Belarus, Uzbekistan)
7. Yandex site: operator for TLDs
"""
import asyncio
import sys
import os
import logging
import signal
import random
from datetime import datetime

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
from sqlalchemy import select, func

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger("smart")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# ── Config ────────────────────────────────────────────────────────────
PROJECT_ID = 18
COMPANY_ID = 1
TARGET_GOAL = 1000
YANDEX_WORKERS = 8
CRONA_BATCH_SIZE = 60
CRONA_PARALLEL = 5
GPT_ANALYSIS_CONCURRENT = 40
GPT_ANALYSIS_BATCH = 40

shutdown_requested = False

def handle_signal(signum, frame):
    global shutdown_requested
    logger.warning("Shutdown requested, finishing current batch...")
    shutdown_requested = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


# ── DIVERSE QUERY STRATEGIES ──────────────────────────────────────────

def generate_smart_queries():
    """Generate diverse queries using multiple search angles."""
    queries = []

    # Strategy 1: Domain pattern searches — find sites with invest/capital/wealth in domain
    domain_patterns = [
        "site:*capital.ru управление активами",
        "site:*invest.ru инвестиционная компания",
        "site:*-am.ru управляющая компания",
        "site:*trust.ru доверительное управление",
        "site:*wealth.ru wealth management",
        "site:*fund.ru инвестиционный фонд",
        "site:*broker.ru инвестиции",
        "site:*.capital инвестиционная компания",
        "site:*.fund управление активами",
        "site:*.finance инвестиционный фонд",
        "site:*.investments wealth management",
    ]
    queries.extend(domain_patterns)

    # Strategy 2: Industry-specific terms (broader than "family office")
    industry_terms = [
        # Asset management
        "управляющая компания реестр ЦБ РФ",
        "лицензия управляющей компании Банк России",
        "реестр управляющих компаний инвестиционных фондов",
        "управление активами лицензия ЦБ",
        "список управляющих компаний ПИФ",
        "рейтинг управляющих компаний России",
        "топ управляющих компаний по объему активов",
        "управляющие компании НПФ",
        "доверительное управление ценными бумагами",
        "доверительное управление активами компания",
        "индивидуальное доверительное управление",
        "стратегии доверительного управления",
        "ДУ для состоятельных клиентов",
        # Private banking
        "private banking Россия",
        "private banking услуги банки",
        "private banking для состоятельных клиентов",
        "приватный банкинг премиальное обслуживание",
        "премиум обслуживание состоятельных клиентов банк",
        # Investment funds
        "инвестиционный фонд прямых инвестиций Россия",
        "фонд прямых инвестиций PE fund Россия",
        "венчурный фонд Россия управление",
        "закрытый паевой инвестиционный фонд ЗПИФ",
        "ЗПИФ недвижимости управляющая компания",
        "ЗПИФ венчурный фонд",
        # Family office
        "семейный офис Россия",
        "family office Russia",
        "создание семейного офиса",
        "услуги семейного офиса",
        "мультисемейный офис",
        "single family office Россия",
    ]
    queries.extend(industry_terms)

    # Strategy 3: Legal/tax for wealthy (these showed up as targets)
    legal_wealth = [
        "юридические услуги для состоятельных клиентов",
        "налоговое планирование для HNWI",
        "структурирование активов юридическая фирма",
        "защита активов юридическая компания Россия",
        "налоговый консалтинг крупный капитал",
        "наследственное планирование состоятельных семей",
        "создание траста в России",
        "трастовые услуги Россия",
        "личный фонд создание Россия",
        "КИК контролируемые иностранные компании консалтинг",
        "деофшоризация активов юристы",
        "международное налоговое планирование",
        "юристы для инвесторов Москва",
        "адвокат для бизнеса инвестиции",
    ]
    queries.extend(legal_wealth)

    # Strategy 4: Crypto/USDT (Deliryo's core service area)
    crypto_finance = [
        "обмен USDT юридические лица Россия",
        "криптовалюта OTC обмен Москва",
        "крипто брокер Россия",
        "USDT рубли обмен компания",
        "криптобиржа Россия P2P",
        "легальный обмен криптовалюты Россия",
        "криптовалютный консалтинг юридический",
        "крипто custody Россия",
    ]
    queries.extend(crypto_finance)

    # Strategy 5: Wealth management conferences/events/directories
    directories_events = [
        "SPEAR'S Russia wealth management",
        "рейтинг wealth management Россия",
        "Forbes wealth management клуб",
        "конференция управление капиталом Россия 2024",
        "конференция private banking Россия",
        "каталог управляющих компаний",
        "справочник инвестиционных компаний Россия",
        "ассоциация управляющих компаний",
        "НАУФОР члены управляющие компании",
        "РСХБ управление активами рейтинг",
        "Investfunds рейтинг управляющих",
        "RAEX рейтинг управляющих компаний",
    ]
    queries.extend(directories_events)

    # Strategy 6: CIS countries (Kazakhstan targets were found!)
    cis = [
        "управление активами Казахстан",
        "wealth management Казахстан Алматы",
        "инвестиционные компании Казахстан",
        "инвестиционные фонды Казахстан",
        "управляющая компания Астана",
        "private banking Казахстан",
        "брокерские компании Казахстан",
        "wealth management Беларусь",
        "инвестиционные компании Минск",
        "управление активами Узбекистан Ташкент",
        "инвестиционные компании СНГ",
        "family office Казахстан",
        "family office СНГ",
    ]
    queries.extend(cis)

    # Strategy 7: Competitor/adjacent searches
    adjacent = [
        "альтернатива банку для крупного капитала",
        "куда инвестировать крупную сумму Россия",
        "независимый финансовый советник Россия",
        "независимый инвестиционный консультант",
        "финансовый советник для HNWI",
        "персональный финансовый консультант",
        "управление наследством компания",
        "благотворительный фонд создание управление",
        "эндаумент фонд управление Россия",
        "инвестиции в коммерческую недвижимость управление",
        "управление портфелем недвижимости компания",
    ]
    queries.extend(adjacent)

    # Strategy 8: Specific niche finance terms
    niche = [
        "мезонинное финансирование Россия",
        "факторинг для крупного бизнеса",
        "секьюритизация активов компания Россия",
        "structured products инвестиции Россия",
        "хедж фонд Россия",
        "commodity trading company Russia",
        "торговля деривативами компания Россия",
        "фонд недвижимости Россия закрытый",
        "art banking коллекционирование инвестиции",
    ]
    queries.extend(niche)

    random.shuffle(queries)
    return queries


# ── Monkey-patch concurrency ─────────────────────────────────────────

def patch_concurrency():
    """Override hardcoded concurrency values in the services."""
    import app.services.company_search_service as css_mod

    original_scrape_analyze = css_mod.CompanySearchService._scrape_and_analyze_domains

    async def patched_scrape_and_analyze(self, session, job, domains, target_segments):
        import asyncio as aio
        from app.services.crona_service import crona_service

        total_tokens = (job.config or {}).get("openai_tokens_used", 0)
        crona_credits_used = 0

        existing_result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == job.project_id,
                SearchResult.domain.in_(domains),
            )
        )
        existing_domains = {row[0] for row in existing_result.fetchall()}
        to_analyze = [d for d in domains if d not in existing_domains]

        if not to_analyze:
            return

        logger.info(f"  Scraping {len(to_analyze)} domains (Crona)")

        scraped_texts = {}
        used_crona = False

        if crona_service.is_configured:
            crona_semaphore = aio.Semaphore(CRONA_PARALLEL)

            async def scrape_crona_batch(batch):
                async with crona_semaphore:
                    return await crona_service.scrape_domains(batch)

            batches = [to_analyze[i:i + CRONA_BATCH_SIZE] for i in range(0, len(to_analyze), CRONA_BATCH_SIZE)]
            batch_results = await aio.gather(
                *[scrape_crona_batch(b) for b in batches],
                return_exceptions=True,
            )
            for result in batch_results:
                if isinstance(result, dict):
                    scraped_texts.update(result)
                elif isinstance(result, Exception):
                    logger.error(f"  Crona batch failed: {result}")

            crona_credits_used = crona_service.credits_used
            used_crona = True
            logger.info(f"  Crona: {len(scraped_texts)}/{len(to_analyze)} scraped, credits={crona_credits_used}")
        else:
            semaphore = aio.Semaphore(10)
            async def scrape_one(domain):
                async with semaphore:
                    html = await self.scrape_domain(domain)
                    scraped_texts[domain] = html
            await aio.gather(*[scrape_one(d) for d in to_analyze], return_exceptions=True)

        scraped_at = datetime.utcnow()
        domain_to_query = (job.config or {}).get("domain_to_query", {})

        logger.info(f"  Analyzing {len(to_analyze)} domains (GPT)")
        semaphore = aio.Semaphore(GPT_ANALYSIS_CONCURRENT)

        async def analyze_domain(domain):
            nonlocal total_tokens
            async with semaphore:
                content = scraped_texts.get(domain)
                source_qid = domain_to_query.get(domain)

                if not content or len(content) < 50:
                    sr = SearchResult(
                        search_job_id=job.id, project_id=job.project_id,
                        domain=domain, url=f"https://{domain}",
                        is_target=False, confidence=0,
                        reasoning="Failed to scrape website",
                        scraped_at=scraped_at, source_query_id=source_qid,
                    )
                    session.add(sr)
                    return

                analysis = await self.analyze_company(
                    content, target_segments, domain, is_html=not used_crona,
                )
                analyzed_at = datetime.utcnow()
                total_tokens += analysis.get("tokens_used", 0)

                sr = SearchResult(
                    search_job_id=job.id, project_id=job.project_id,
                    domain=domain, url=f"https://{domain}",
                    is_target=analysis.get("is_target", False),
                    confidence=analysis.get("confidence", 0),
                    reasoning=analysis.get("reasoning", ""),
                    company_info=analysis.get("company_info", {}),
                    scores=analysis.get("scores", {}),
                    html_snippet=content[:2000],
                    scraped_at=scraped_at, analyzed_at=analyzed_at,
                    source_query_id=source_qid,
                )
                session.add(sr)

        for i in range(0, len(to_analyze), GPT_ANALYSIS_BATCH):
            batch = to_analyze[i:i + GPT_ANALYSIS_BATCH]
            tasks = [analyze_domain(d) for d in batch]
            await aio.gather(*tasks, return_exceptions=True)
            await session.flush()

        config = dict(job.config or {})
        config["openai_tokens_used"] = total_tokens
        config["crona_credits_used"] = config.get("crona_credits_used", 0) + crona_credits_used
        config["scrape_method"] = "crona" if used_crona else "httpx"
        job.config = config

    css_mod.CompanySearchService._scrape_and_analyze_domains = patched_scrape_and_analyze
    settings.SEARCH_WORKERS = YANDEX_WORKERS


# ── Main ─────────────────────────────────────────────────────────────

async def run_smart_search():
    patch_concurrency()

    all_queries = generate_smart_queries()
    logger.info(f"Generated {len(all_queries)} diverse queries across 8 strategies")

    async with async_session_maker() as session:
        project = (await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )).scalar_one_or_none()
        if not project:
            logger.error(f"Project {PROJECT_ID} not found!")
            return

        existing = await company_search_service._count_project_targets(session, PROJECT_ID)
        logger.info(f"Project: {project.name} | Current targets: {existing}/{TARGET_GOAL}")

        if existing >= TARGET_GOAL:
            logger.info("Target goal already reached!")
            return

        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.RUNNING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=0,
            project_id=PROJECT_ID,
            started_at=datetime.utcnow(),
            config={
                "smart_mode": True,
                "strategy": "diverse_angles",
                "total_strategies": 8,
                "target_goal": TARGET_GOAL,
                "target_segments": project.target_segments,
            },
        )
        session.add(job)
        await session.commit()
        logger.info(f"Created smart search job #{job.id}")

        run_start = datetime.utcnow()
        prev_targets = existing
        batch_size = 25  # Smaller batches for faster feedback
        batch_num = 0

        for i in range(0, len(all_queries), batch_size):
            if shutdown_requested or existing >= TARGET_GOAL:
                break

            batch = all_queries[i:i + batch_size]
            batch_num += 1
            elapsed = (datetime.utcnow() - run_start).total_seconds()
            new_total = existing - prev_targets + (existing - 238)  # total new since script start
            rate = (existing - prev_targets) / max(elapsed / 60, 0.01) if elapsed > 0 else 0

            logger.info(f"\n--- BATCH {batch_num} ({i+1}-{i+len(batch)}/{len(all_queries)}) | "
                        f"targets={existing}/{TARGET_GOAL} | "
                        f"rate={rate:.1f}/min | {elapsed/60:.1f}min ---")

            for q_text in batch:
                sq = SearchQuery(search_job_id=job.id, query_text=q_text)
                session.add(sq)
            job.queries_total = (job.queries_total or 0) + len(batch)
            await session.commit()

            # Run Yandex search
            t0 = datetime.utcnow()
            await search_service.run_search_job(session, job.id)
            await session.refresh(job)
            dt = (datetime.utcnow() - t0).total_seconds()
            logger.info(f"  Yandex: {dt:.0f}s | found={job.domains_found} new={job.domains_new}")

            # Get new domains
            skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
            new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
            logger.info(f"  New domains to analyze: {len(new_domains)} (skip set: {len(skip_set)})")

            if new_domains:
                t0 = datetime.utcnow()
                await company_search_service._scrape_and_analyze_domains(
                    session=session, job=job,
                    domains=new_domains,
                    target_segments=project.target_segments,
                )
                dt = (datetime.utcnow() - t0).total_seconds()
                logger.info(f"  Scrape+analyze: {dt:.0f}s")

            await session.commit()

            # Auto-review
            try:
                from app.services.review_service import review_service
                stats = await review_service.review_batch(session, job.id, project.target_segments)
                await session.commit()
                confirmed = stats.get('confirmed', 0)
                rejected = stats.get('rejected', 0)
                if confirmed or rejected:
                    logger.info(f"  Review: +{confirmed} confirmed, -{rejected} rejected")
            except Exception as e:
                logger.warning(f"  Review failed: {e}")

            # Count targets
            new_existing = await company_search_service._count_project_targets(session, PROJECT_ID)
            delta = new_existing - existing
            existing = new_existing

            if delta > 0:
                logger.info(f"  *** +{delta} NEW TARGETS! *** Total: {existing}/{TARGET_GOAL}")
            else:
                logger.info(f"  +0 targets | total: {existing}/{TARGET_GOAL}")

            # Show sample queries from this batch
            if batch_num <= 3 or delta > 0:
                logger.info(f"  Queries: {batch[:3]}")

        # Complete
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        config = dict(job.config or {})
        config["final_targets"] = existing
        config["batches_run"] = batch_num
        config["queries_used"] = min(i + batch_size, len(all_queries))
        job.config = config
        await session.commit()

        total_elapsed = (datetime.utcnow() - run_start).total_seconds()
        new_targets = existing - prev_targets
        logger.info(f"\n{'='*60}")
        logger.info(f"SMART SEARCH COMPLETE")
        logger.info(f"  New targets: +{new_targets} (was {prev_targets}, now {existing})")
        logger.info(f"  Queries used: {min(i + batch_size, len(all_queries))}/{len(all_queries)}")
        logger.info(f"  Time: {total_elapsed/60:.1f}min")
        logger.info(f"  Rate: {new_targets / max(total_elapsed/60, 0.01):.1f} targets/min")
        logger.info(f"{'='*60}")


async def main():
    try:
        await run_smart_search()
    except Exception as e:
        logger.error(f"Smart search crashed: {e}", exc_info=True)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
