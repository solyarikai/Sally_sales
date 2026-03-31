"""Background offer scraper — analyzes websites for all projects missing offers."""
import asyncio
import logging
import re
import json

import httpx
from sqlalchemy import select

from app.db import async_session_maker
from app.models.project import Project
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value

logger = logging.getLogger(__name__)


async def scrape_pending_offers():
    """Find all projects with website but no offer_summary, scrape and analyze them."""
    async with async_session_maker() as session:
        # Find projects needing offer analysis
        result = await session.execute(
            select(Project).where(
                Project.website.isnot(None),
                Project.offer_summary.is_(None),
                Project.is_active == True,
            )
        )
        projects = result.scalars().all()

        if not projects:
            logger.info("Offer scraper: no pending projects")
            return

        logger.info(f"Offer scraper: {len(projects)} projects need offer analysis")

        for project in projects:
            try:
                await _analyze_project_offer(session, project)
                await session.commit()
            except Exception as e:
                logger.error(f"Offer scraper failed for project {project.id}: {e}")
                await session.rollback()


async def _analyze_project_offer(session, project: Project):
    """Run 3-layer offer extraction for a single project."""
    website = project.website
    if not website:
        return

    if not website.startswith("http"):
        website = f"https://{website}"

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
        logger.info(f"Offer scraper: project {project.id} — no OpenAI key, skipping")
        return

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
        logger.warning(f"Offer scraper proxy: {e}")

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

    # Layer 3: GPT analysis (from text or knowledge)
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
                logger.info(f"Offer scraper: GPT doesn't know {dom}")
                return

            if wt:
                offer["_raw_website_text"] = wt[:2000]
            offer["_source"] = "website" if wt else "gpt_knowledge"

            project.offer_summary = offer
            project.target_segments = f"{offer.get('primary_offer', '')}. Target: {offer.get('target_audience', '')}"
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(project, "offer_summary")

            logger.info(f"Offer scraper: analyzed {dom} for project {project.id} — {offer.get('primary_offer', '')[:80]}")

    except Exception as e:
        logger.error(f"Offer scraper GPT failed for {dom}: {e}")


def start_offer_scraper():
    """Run offer scraper once on startup, then every 5 minutes."""
    async def _loop():
        await asyncio.sleep(10)  # Wait for DB to be ready
        while True:
            try:
                await scrape_pending_offers()
            except Exception as e:
                logger.error(f"Offer scraper loop error: {e}")
            await asyncio.sleep(300)  # Every 5 min

    asyncio.get_event_loop().create_task(_loop())
