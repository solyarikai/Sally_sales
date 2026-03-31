"""Background offer scraper — analyzes websites for all projects missing offers.

Architecture:
1. INLINE: create_project does 3-layer scrape during the tool call (immediate)
2. BACKGROUND: this service catches anything missed (session broke, timeout, etc.)
   - Runs 5s after startup, then every 30s
   - Max 3 retries per project, then marks as failed
   - Can also be triggered on-demand via trigger_offer_analysis(project_id)
"""
import asyncio
import logging
import re
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, or_
from sqlalchemy.orm.attributes import flag_modified

from app.db import async_session_maker
from app.models.project import Project
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
_pending_ids: set[int] = set()  # Projects queued for immediate analysis


def queue_offer_analysis(project_id: int):
    """Queue a project for immediate offer analysis (called from create_project)."""
    _pending_ids.add(project_id)


async def scrape_pending_offers():
    """Find all projects needing offer analysis, process them."""
    async with async_session_maker() as session:
        # Priority 1: explicitly queued projects (from create_project)
        queued = list(_pending_ids)
        _pending_ids.clear()

        # Priority 2: projects with website + no offer + retries left
        result = await session.execute(
            select(Project).where(
                Project.website.isnot(None),
                Project.website != "",
                Project.is_active == True,
                or_(
                    Project.offer_summary.is_(None),
                    Project.offer_summary == {},
                ),
            )
        )
        db_projects = result.scalars().all()

        # Merge: queued first, then DB scan (dedup by id)
        seen = set()
        projects = []

        # Add queued projects
        if queued:
            queued_result = await session.execute(
                select(Project).where(Project.id.in_(queued))
            )
            for p in queued_result.scalars().all():
                if p.id not in seen:
                    projects.append(p)
                    seen.add(p.id)

        # Add DB-scanned projects
        for p in db_projects:
            if p.id not in seen:
                # Check retry count
                retries = (p.offer_summary or {}).get("_retries", 0) if isinstance(p.offer_summary, dict) else 0
                if retries < MAX_RETRIES:
                    projects.append(p)
                    seen.add(p.id)

        if not projects:
            return  # Silent — no spam in logs

        logger.info(f"Offer scraper: {len(projects)} projects to analyze")

        for project in projects:
            try:
                success = await _analyze_project_offer(session, project)
                await session.commit()
                if success:
                    logger.info(f"Offer scraper: ✓ {project.name} (id={project.id})")
            except Exception as e:
                logger.error(f"Offer scraper failed for {project.id}: {e}")
                await session.rollback()


async def _analyze_project_offer(session, project: Project) -> bool:
    """Run 3-layer offer extraction. Returns True if offer was extracted."""
    website = project.website
    if not website:
        return False
    if not website.startswith("http"):
        website = f"https://{website}"

    # Track retries
    retries = 0
    if isinstance(project.offer_summary, dict):
        retries = project.offer_summary.get("_retries", 0)

    # Get user's keys
    openai_row = (await session.execute(
        select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.user_id == project.user_id,
            MCPIntegrationSetting.integration_name == "openai",
            MCPIntegrationSetting.is_connected == True,
        )
    )).scalar_one_or_none()
    openai_key = decrypt_value(openai_row.api_key_encrypted) if openai_row else None
    if not openai_key:
        return False

    apify_row = (await session.execute(
        select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.user_id == project.user_id,
            MCPIntegrationSetting.integration_name == "apify",
            MCPIntegrationSetting.is_connected == True,
        )
    )).scalar_one_or_none()
    apify_key = decrypt_value(apify_row.api_key_encrypted) if apify_row else None

    wt = ""  # website text

    # Layer 1: Apify proxy scrape
    try:
        from app.services.scraper_service import ScraperService
        scraper = ScraperService(apify_proxy_password=apify_key)
        r = await scraper.scrape_website(website)
        wt = r.get("text", "")[:4000]
    except Exception as e:
        logger.debug(f"Proxy scrape {website}: {e}")

    # Layer 2: Direct fetch + meta tags
    if not wt:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                resp = await c.get(website, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    h = resp.text
                    mp = []
                    for p in [r'<meta\s+name="description"\s+content="([^"]+)"',
                              r'<meta\s+property="og:description"\s+content="([^"]+)"',
                              r'<title>([^<]+)</title>']:
                        m = re.search(p, h, re.IGNORECASE)
                        if m:
                            mp.append(m.group(1).strip())
                    b = re.sub(r'<script[^>]*>.*?</script>', '', h, flags=re.DOTALL | re.IGNORECASE)
                    b = re.sub(r'<style[^>]*>.*?</style>', '', b, flags=re.DOTALL | re.IGNORECASE)
                    b = re.sub(r'<[^>]+>', ' ', b)
                    b = re.sub(r'\s+', ' ', b).strip()[:4000]
                    wt = b if len(b) > 100 else ("Meta: " + " | ".join(mp) if mp else "")
        except Exception:
            pass

    # Layer 3: GPT analysis (scraped text OR GPT knowledge)
    dom = website.replace("https://", "").replace("http://", "").rstrip("/")
    if wt:
        prompt = f"Analyze this company website.\nWebsite: {website}\nContent: {wt[:3000]}\n\n"
    else:
        prompt = f"What does the company at {dom} do? Use your knowledge.\n\n"

    prompt += ('Return JSON: {"company_name":"...","products":[{"name":"...","description":"..."}],'
               '"primary_offer":"main product in 1 sentence","value_proposition":"problem solved",'
               '"target_audience":"who buys","key_differentiators":["..."]}\n'
               'If unknown: {"unknown":true}\nOnly JSON.')

    try:
        async with httpx.AsyncClient(timeout=25) as c:
            rr = await c.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 800, "temperature": 0})
            ct = rr.json()["choices"][0]["message"]["content"].strip()
            if ct.startswith("```"):
                ct = ct.split("\n", 1)[1].rsplit("```", 1)[0]
            offer = json.loads(ct)

            if offer.get("unknown"):
                # Mark as failed with retry count
                project.offer_summary = {"_retries": retries + 1, "_failed": True,
                                         "_reason": "GPT doesn't know this company",
                                         "_last_attempt": datetime.now(timezone.utc).isoformat()}
                flag_modified(project, "offer_summary")
                return False

            if wt:
                offer["_raw_website_text"] = wt[:2000]
            offer["_source"] = "website" if wt else "gpt_knowledge"
            offer["_analyzed_at"] = datetime.now(timezone.utc).isoformat()

            project.offer_summary = offer
            project.target_segments = f"{offer.get('primary_offer', '')}. Target: {offer.get('target_audience', '')}"
            flag_modified(project, "offer_summary")
            return True

    except Exception as e:
        # Track retry
        project.offer_summary = {"_retries": retries + 1, "_error": str(e)[:200],
                                 "_last_attempt": datetime.now(timezone.utc).isoformat()}
        flag_modified(project, "offer_summary")
        logger.error(f"Offer GPT failed for {dom}: {e}")
        return False


def start_offer_scraper():
    """Run offer scraper on startup + every 30 seconds."""
    async def _loop():
        await asyncio.sleep(5)  # Quick startup
        while True:
            try:
                await scrape_pending_offers()
            except Exception as e:
                logger.error(f"Offer scraper loop: {e}")
            await asyncio.sleep(30)  # Every 30s — fast pickup

    asyncio.get_event_loop().create_task(_loop())
