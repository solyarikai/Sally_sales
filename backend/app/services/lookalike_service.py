"""
Lookalike Service — Analyze qualified leads, cluster by business model,
then find lookalike companies via Apollo → Yandex → Google.

Phase 1: Scrape + GPT analysis per contact → cluster via Gemini
Phase 2: Generate search strategy per cluster
Phase 3: Execute search (Apollo → Yandex → Google), reuse existing analyze pipeline
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.core.config import settings
from app.db import async_session_maker
from app.models.contact import Contact, Project
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchQueryStatus, SearchResult,
)
from app.models.lookalike import (
    LookalikeCluster, ClusterMember, LookalikeRun,
    LookalikeRunStatus, LookalikePhase,
)
from app.models.reply import ProcessedReply
from app.services.company_search_service import company_search_service
from app.services.gemini_client import gemini_generate, extract_json_from_gemini

logger = logging.getLogger(__name__)

# Concurrency limits
_scrape_semaphore = asyncio.Semaphore(10)
_gpt_semaphore = asyncio.Semaphore(20)


class _VirtualContact:
    """Lightweight stand-in for Contact model, used for warm-reply domains
    that don't have a real Contact record."""
    def __init__(self, id, domain, company_name, first_name, last_name, job_title, status):
        self.id = id
        self.domain = domain
        self.company_name = company_name
        self.first_name = first_name
        self.last_name = last_name
        self.job_title = job_title
        self.status = status


class LookalikeService:

    # ------------------------------------------------------------------ #
    # Phase 1: Analyze contacts + Cluster
    # ------------------------------------------------------------------ #

    async def analyze_and_cluster(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        offers: List[Dict[str, Any]],
    ) -> List[LookalikeCluster]:
        """
        1. Fetch qualified leads for project
        2. Scrape + GPT-analyze each contact's domain
        3. Gemini clustering by business model
        4. Persist clusters + members
        """
        # 1. Get qualified contacts with domains
        result = await session.execute(
            select(Contact).where(
                Contact.project_id == project_id,
                Contact.status == "qualified",
                Contact.domain.isnot(None),
                Contact.deleted_at.is_(None),
            )
        )
        contacts = list(result.scalars().all())

        # 1b. Also get warm-reply domains from processed_replies
        # These are leads who replied with interest but may not be in contacts table
        project_result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        campaign_filters = project.campaign_filters or [] if project else []

        warm_reply_contacts = []
        if campaign_filters:
            warm_categories = ["interested", "meeting_request", "question"]
            pr_result = await session.execute(
                select(ProcessedReply).where(
                    ProcessedReply.campaign_name.in_(campaign_filters),
                    ProcessedReply.category.in_(warm_categories),
                )
            )
            warm_replies = list(pr_result.scalars().all())

            # Deduplicate by domain, skip personal emails
            personal_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                              "mail.ru", "yandex.ru", "icloud.com", "protonmail.com", "aol.com"}
            existing_domains = {c.domain for c in contacts if c.domain}
            seen_domains = set()

            for pr in warm_replies:
                if not pr.lead_email or "@" not in pr.lead_email:
                    continue
                domain = pr.lead_email.split("@")[1].lower()
                if domain in personal_domains or domain in existing_domains or domain in seen_domains:
                    continue
                seen_domains.add(domain)
                # Create a lightweight object that _analyze_contacts can handle
                warm_reply_contacts.append(_VirtualContact(
                    id=-(len(warm_reply_contacts) + 1),  # negative IDs for virtual contacts
                    domain=domain,
                    company_name=pr.lead_company or domain,
                    first_name=pr.lead_first_name,
                    last_name=pr.lead_last_name,
                    job_title=None,
                    status=f"warm_reply:{pr.category}",
                ))

            logger.info(f"[TAM] Found {len(warm_reply_contacts)} unique warm-reply domains (from {len(warm_replies)} replies)")

        all_contacts = contacts + warm_reply_contacts
        if not all_contacts:
            raise ValueError(f"No qualified/warm contacts with domains found for project {project_id}")

        logger.info(f"[TAM] Phase 1: analyzing {len(all_contacts)} contacts ({len(contacts)} qualified + {len(warm_reply_contacts)} warm replies) for project {project_id}")

        # 2. Scrape + analyze each contact
        analyses = await self._analyze_contacts(all_contacts, offers)

        # 3. Cluster via Gemini
        clusters_data = await self._cluster_contacts(analyses, offers, project_id)

        # 4. Persist
        clusters = await self._persist_clusters(
            session, clusters_data, analyses, project_id, company_id
        )

        logger.info(f"[TAM] Phase 1 complete: {len(clusters)} clusters created")
        return clusters

    async def _analyze_contacts(
        self,
        contacts: List[Contact],
        offers: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Scrape website + GPT-4o-mini analysis for each contact."""
        offers_text = "\n".join(
            f"- {o['id']}: {o['name']} — {o['description']}"
            for o in offers
        )

        async def analyze_one(contact: Contact) -> Dict[str, Any]:
            domain = contact.domain
            if not domain:
                return {"contact_id": contact.id, "domain": None, "error": "no domain"}

            # Scrape
            async with _scrape_semaphore:
                text = await self._scrape_domain(domain)

            if not text or len(text) < 50:
                return {
                    "contact_id": contact.id, "domain": domain,
                    "error": "scrape failed or too short",
                    "website_scraped": False,
                }

            # GPT analysis
            async with _gpt_semaphore:
                analysis = await self._gpt_analyze_contact(
                    domain, text, contact, offers_text
                )

            return {
                "contact_id": contact.id,
                "domain": domain,
                "company_name": contact.company_name or domain,
                "contact_status": contact.status,
                "website_scraped": True,
                "analysis": analysis,
            }

        tasks = [analyze_one(c) for c in contacts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"[TAM] Contact analysis error: {r}")
                continue
            if r.get("analysis"):
                analyses.append(r)

        logger.info(f"[TAM] Analyzed {len(analyses)}/{len(contacts)} contacts successfully")
        return analyses

    async def _scrape_domain(self, domain: str) -> Optional[str]:
        """Scrape domain using httpx (reuses company_search_service extraction)."""
        url = f"https://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=15, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"}
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                clean = company_search_service._extract_clean_text(
                    resp.text, domain, is_html=True
                )
                return clean.get("text", "")
        except Exception as e:
            logger.debug(f"[TAM] Scrape failed for {domain}: {e}")
            return None

    async def _gpt_analyze_contact(
        self,
        domain: str,
        text: str,
        contact: Contact,
        offers_text: str,
    ) -> Dict[str, Any]:
        """GPT-4o-mini: describe business model + map offer fit."""
        prompt = f"""Analyze this company's website and determine their PRECISE business model and which of our offers would fit them.

COMPANY: {contact.company_name or domain}
DOMAIN: {domain}
CONTACT: {contact.first_name or ''} {contact.last_name or ''}, {contact.job_title or ''}

WEBSITE TEXT (first 3000 chars):
{text[:3000]}

OUR OFFERS:
{offers_text}

Respond in JSON:
{{
  "business_model": "2-3 sentence precise description of what this company does, their customers, and revenue model",
  "industry": "specific industry (e.g. 'iGaming', 'crypto exchange', 'freelance marketplace')",
  "offer_fit": ["offer_id1", "offer_id2"],
  "offer_fit_reasoning": "why these offers fit",
  "company_size_signal": "startup/smb/mid/enterprise based on website signals",
  "geography": "where they operate"
}}"""

        api_key = settings.OPENAI_API_KEY
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a B2B sales analyst. Analyze companies precisely."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    start = content.find("{")
                    end = content.rfind("}")
                    if start != -1 and end != -1:
                        return json.loads(content[start:end + 1])
                    return {"business_model": content, "offer_fit": []}
        except Exception as e:
            logger.error(f"[TAM] GPT analysis failed for {domain}: {e}")
            return {"business_model": f"Analysis failed: {e}", "offer_fit": [], "error": str(e)}

    async def _cluster_contacts(
        self,
        analyses: List[Dict[str, Any]],
        offers: List[Dict[str, Any]],
        project_id: int,
    ) -> List[Dict[str, Any]]:
        """Gemini 2.5: cluster contacts by business model similarity.

        Uses sequential indices (0, 1, 2, ...) instead of contact_ids to avoid
        Gemini hallucinating wrong IDs. Maps back after parsing.
        """
        # Build indexed list — Gemini sees indices, we map back to contact_ids
        contacts_summary = []
        index_to_contact_id = {}
        for idx, a in enumerate(analyses):
            analysis = a.get("analysis", {})
            index_to_contact_id[idx] = a["contact_id"]
            contacts_summary.append({
                "idx": idx,
                "domain": a["domain"],
                "company": a.get("company_name", a["domain"]),
                "lead_status": a.get("contact_status", "qualified"),
                "business_model": analysis.get("business_model", "unknown"),
                "industry": analysis.get("industry", "unknown"),
                "offer_fit": analysis.get("offer_fit", []),
                "geography": analysis.get("geography", "unknown"),
            })

        offers_text = json.dumps(offers, indent=2)

        system_prompt = """You are a B2B market analyst specializing in customer segmentation for payment infrastructure companies.

Your task: group these qualified leads into precise clusters based on HOW they would USE our client's payment/crypto services — not by generic industry.

Rules:
- Create 3-8 clusters. Each cluster = a specific USE CASE for our offers
- Cluster name = precise business model + why they need our offer (e.g. "iGaming platforms needing crypto payouts for affiliates" NOT "Technology companies")
- Every company must be in exactly one cluster
- business_model = 2-3 sentences: what companies in this cluster do, who their customers are, and WHY they specifically need our payment/crypto services
- If 1-2 companies don't fit, put them in a "Misc" cluster
- The indices array must use the exact idx values from the input — do NOT invent new indices"""

        user_prompt = f"""Here are {len(contacts_summary)} leads (qualified + warm replies) to cluster:

{json.dumps(contacts_summary, indent=2)}

Available offers from our client:
{offers_text}

IMPORTANT: Use the "idx" field values in the "indices" arrays. Every idx from 0 to {len(contacts_summary) - 1} must appear in exactly one cluster.

Respond in JSON:
{{
  "clusters": [
    {{
      "name": "Precise use-case description (max 10 words)",
      "business_model": "2-3 sentences: what these companies do, their customers, why they need our offer",
      "offer_fit": ["offer_id1"],
      "indices": [0, 3, 7]
    }}
  ]
}}"""

        prompt_size = len(json.dumps(contacts_summary))
        logger.info(f"[TAM] Sending {len(contacts_summary)} contacts to Gemini for clustering (prompt ~{prompt_size} chars)")

        result = await gemini_generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=16000,
            thinking_budget=4000,  # cap thinking to leave room for JSON output
            model="gemini-2.5-flash",
            project_id=project_id,
        )

        logger.info(f"[TAM] Gemini response: {len(result.get('content', ''))} chars, tokens={result.get('tokens', {})}")

        content = extract_json_from_gemini(result["content"])
        try:
            parsed = json.loads(content)
            raw_clusters = parsed.get("clusters", [])
        except json.JSONDecodeError:
            logger.error(f"[TAM] Failed to parse Gemini clustering response (first 1000 chars): {content[:1000]}")
            raw_clusters = []

        # Map indices back to contact_ids
        all_valid_indices = set(range(len(analyses)))
        assigned_indices = set()
        clusters_out = []

        for rc in raw_clusters:
            # Accept both "indices" and "contact_ids" keys for robustness
            indices = rc.get("indices", rc.get("contact_ids", []))
            # Filter to valid indices only
            valid = [i for i in indices if i in all_valid_indices]
            if not valid:
                continue
            assigned_indices.update(valid)
            clusters_out.append({
                "name": rc["name"],
                "business_model": rc.get("business_model", ""),
                "offer_fit": rc.get("offer_fit", []),
                "contact_ids": [index_to_contact_id[i] for i in valid],
            })

        # Put unassigned contacts into a Misc cluster
        unassigned = all_valid_indices - assigned_indices
        if unassigned:
            clusters_out.append({
                "name": "Misc / Other business models",
                "business_model": "Companies that don't fit neatly into other clusters",
                "offer_fit": [],
                "contact_ids": [index_to_contact_id[i] for i in sorted(unassigned)],
            })

        # Fallback: if parsing totally failed, single cluster
        if not clusters_out:
            logger.warning("[TAM] Clustering produced 0 clusters, using single fallback")
            clusters_out = [{
                "name": "All qualified leads",
                "business_model": "Mixed business models",
                "offer_fit": [],
                "contact_ids": [a["contact_id"] for a in analyses],
            }]

        logger.info(f"[TAM] Gemini produced {len(clusters_out)} clusters from {len(analyses)} contacts")
        return clusters_out

    async def _persist_clusters(
        self,
        session: AsyncSession,
        clusters_data: List[Dict[str, Any]],
        analyses: List[Dict[str, Any]],
        project_id: int,
        company_id: int,
    ) -> List[LookalikeCluster]:
        """Create LookalikeCluster + ClusterMember records."""
        # Build lookup: contact_id -> analysis
        analysis_map = {a["contact_id"]: a for a in analyses}

        clusters = []
        for cd in clusters_data:
            contact_ids = cd.get("contact_ids", [])
            # Filter to only valid contact_ids that exist in our analyses
            valid_ids = [cid for cid in contact_ids if cid in analysis_map]
            if not valid_ids and contact_ids:
                logger.warning(f"[TAM] Cluster '{cd['name']}' has {len(contact_ids)} IDs but none match analyses — skipping")
                continue

            cluster = LookalikeCluster(
                project_id=project_id,
                company_id=company_id,
                name=cd["name"],
                business_model=cd.get("business_model", ""),
                offer_fit=cd.get("offer_fit", []),
                qualified_lead_count=len(valid_ids),
            )
            session.add(cluster)
            await session.flush()  # get cluster.id

            # Add members (skip virtual contacts with negative IDs — no real Contact record)
            for cid in valid_ids:
                analysis = analysis_map.get(cid, {})
                if cid < 0:
                    # Virtual warm-reply contact — store analysis in cluster's search_strategy
                    logger.info(f"[TAM] Skipping virtual contact {cid} ({analysis.get('domain')}) for cluster member")
                    continue
                member = ClusterMember(
                    cluster_id=cluster.id,
                    contact_id=cid,
                    business_model_description=analysis.get("analysis", {}).get("business_model", ""),
                    offer_fit=analysis.get("analysis", {}).get("offer_fit", []),
                    website_scraped=analysis.get("website_scraped", False),
                    analysis_data=analysis.get("analysis"),
                )
                session.add(member)

            clusters.append(cluster)

        await session.commit()
        return clusters

    # ------------------------------------------------------------------ #
    # Phase 2: Generate Search Strategy per Cluster
    # ------------------------------------------------------------------ #

    async def generate_cluster_strategy(
        self,
        session: AsyncSession,
        cluster_id: int,
    ) -> LookalikeCluster:
        """Generate search strategy for a cluster using Gemini."""
        result = await session.execute(
            select(LookalikeCluster).where(LookalikeCluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")

        # Get member details for context
        members_result = await session.execute(
            select(ClusterMember).where(ClusterMember.cluster_id == cluster_id)
        )
        members = list(members_result.scalars().all())

        member_descriptions = []
        for m in members:
            desc = m.business_model_description or "unknown"
            member_descriptions.append(desc)

        system_prompt = """You are a B2B sales strategist. Generate a search strategy to find MORE companies similar to the ones in this cluster.
The strategy will be used for:
1. Apollo API search (keyword_tags + locations)
2. Yandex search engine queries (Russian web)
3. Google search engine queries (English web)
4. Domain analysis (scoring criteria)"""

        user_prompt = f"""CLUSTER: {cluster.name}
BUSINESS MODEL: {cluster.business_model}
OFFERS THAT FIT: {json.dumps(cluster.offer_fit)}

EXAMPLE COMPANIES IN CLUSTER ({len(members)} total):
{chr(10).join(f'- {d}' for d in member_descriptions[:10])}

Generate a comprehensive search strategy in JSON:
{{
  "apollo_keywords": ["keyword1", "keyword2"],
  "apollo_locations": ["Country1", "Country2"],
  "yandex_queries": ["query1 in Russian if relevant", "query2"],
  "google_queries": ["query1 in English", "query2"],
  "doc_keywords": ["keyword to find on website", "another keyword"],
  "anti_keywords": ["exclude this type", "not this"],
  "analysis_prompt_override": "Detailed description of what makes a company a target for this cluster. Include: what services/products they should offer, what customers they serve, what business model they follow. This replaces the generic target_segments for scoring."
}}

IMPORTANT:
- apollo_keywords: 3-8 specific industry terms (not generic like 'technology')
- yandex/google queries: 10-20 precise queries using site patterns, quoted phrases, industry jargon
- analysis_prompt_override: must be specific enough to distinguish good matches from generic companies
- doc_keywords: words that would appear on a target company's website"""

        result = await gemini_generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=4000,
            project_id=cluster.project_id,
        )

        content = extract_json_from_gemini(result["content"])
        try:
            strategy = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"[TAM] Failed to parse strategy for cluster {cluster_id}: {content[:500]}")
            strategy = {
                "apollo_keywords": [],
                "yandex_queries": [],
                "google_queries": [],
                "doc_keywords": [],
                "anti_keywords": [],
                "analysis_prompt_override": cluster.business_model,
            }

        cluster.search_strategy = strategy
        await session.commit()

        logger.info(f"[TAM] Strategy generated for cluster {cluster_id}: "
                    f"{len(strategy.get('apollo_keywords', []))} apollo keywords, "
                    f"{len(strategy.get('yandex_queries', []))} yandex queries")
        return cluster

    # ------------------------------------------------------------------ #
    # Phase 3: Execute Search
    # ------------------------------------------------------------------ #

    async def run_cluster_search(
        self,
        cluster_id: int,
        company_id: int,
        budget_apollo: int = 500,
        budget_yandex: int = 200,
        budget_google: int = 50,
    ) -> int:
        """
        Execute phased search for a cluster: Apollo → Yandex → Google.
        Runs in background with own DB session. Returns run_id.
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(LookalikeCluster).where(LookalikeCluster.id == cluster_id)
            )
            cluster = result.scalar_one_or_none()
            if not cluster:
                raise ValueError(f"Cluster {cluster_id} not found")
            if not cluster.search_strategy:
                raise ValueError(f"Cluster {cluster_id} has no search strategy — generate one first")

            run = LookalikeRun(
                cluster_id=cluster_id,
                project_id=cluster.project_id,
                company_id=company_id,
                status=LookalikeRunStatus.PENDING,
                budget_apollo_credits=budget_apollo,
                budget_yandex_queries=budget_yandex,
                budget_google_queries=budget_google,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        # Launch background execution
        asyncio.create_task(self._execute_run(run_id))
        return run_id

    async def _execute_run(self, run_id: int) -> None:
        """Background: execute all phases of a lookalike run."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(LookalikeRun).where(LookalikeRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                return

            result = await session.execute(
                select(LookalikeCluster).where(LookalikeCluster.id == run.cluster_id)
            )
            cluster = result.scalar_one_or_none()
            if not cluster or not cluster.search_strategy:
                run.status = LookalikeRunStatus.FAILED
                run.error_message = "Cluster or strategy not found"
                await session.commit()
                return

            strategy = cluster.search_strategy
            run.status = LookalikeRunStatus.RUNNING
            run.started_at = datetime.utcnow()
            run.stats = {}
            await session.commit()

            target_segments = strategy.get("analysis_prompt_override", cluster.business_model)
            # Ensure "international" keyword is present so _validate_analysis
            # doesn't auto-reject non-Russian sites (cyrillic_ratio hard rule)
            if "international" not in target_segments.lower():
                target_segments += "\n\nTarget geography: international (all countries)"
            total_lookalikes = 0

            try:
                # Phase 1: Apollo
                if strategy.get("apollo_keywords") and run.budget_apollo_credits > 0:
                    run.current_phase = LookalikePhase.APOLLO
                    await session.commit()

                    apollo_count = await self._run_apollo_phase(
                        session, run, cluster, strategy, target_segments
                    )
                    total_lookalikes += apollo_count
                    run.stats["apollo"] = {"targets_found": apollo_count}
                    cluster.apollo_companies_found = apollo_count
                    await session.commit()

                # Phase 2: Yandex
                if strategy.get("yandex_queries") and run.budget_yandex_queries > 0:
                    run.current_phase = LookalikePhase.YANDEX
                    await session.commit()

                    yandex_count = await self._run_yandex_phase(
                        session, run, cluster, strategy, target_segments
                    )
                    total_lookalikes += yandex_count
                    run.stats["yandex"] = {"targets_found": yandex_count}
                    cluster.yandex_targets_found = yandex_count
                    await session.commit()

                # Phase 3: Google (only if budget allows)
                if strategy.get("google_queries") and run.budget_google_queries > 0:
                    run.current_phase = LookalikePhase.GOOGLE
                    await session.commit()

                    google_count = await self._run_google_phase(
                        session, run, cluster, strategy, target_segments
                    )
                    total_lookalikes += google_count
                    run.stats["google"] = {"targets_found": google_count}
                    cluster.google_targets_found = google_count
                    await session.commit()

                run.status = LookalikeRunStatus.COMPLETED
                run.completed_at = datetime.utcnow()
                run.total_lookalikes_found = total_lookalikes
                cluster.total_lookalikes = (cluster.total_lookalikes or 0) + total_lookalikes
                await session.commit()

                logger.info(f"[TAM] Run {run_id} completed: {total_lookalikes} lookalikes found")

            except Exception as e:
                logger.error(f"[TAM] Run {run_id} failed: {e}", exc_info=True)
                run.status = LookalikeRunStatus.FAILED
                run.error_message = str(e)[:500]
                await session.commit()

    async def _run_apollo_phase(
        self,
        session: AsyncSession,
        run: LookalikeRun,
        cluster: LookalikeCluster,
        strategy: Dict[str, Any],
        target_segments: str,
    ) -> int:
        """Apollo org search → scrape + analyze with cluster-specific scoring."""
        from app.services.apollo_service import apollo_service

        keywords = strategy.get("apollo_keywords", [])
        locations = strategy.get("apollo_locations", [])

        logger.info(f"[TAM] Apollo phase: {keywords} × {locations}")

        # Create a SearchJob for tracking
        job = SearchJob(
            company_id=run.company_id,
            project_id=run.project_id,
            cluster_id=cluster.id,
            status=SearchJobStatus.RUNNING,
            search_engine=SearchEngine.APOLLO_ORG,
            started_at=datetime.utcnow(),
            config={"keywords": keywords, "locations": locations},
        )
        session.add(job)
        await session.flush()
        run.apollo_job_id = job.id
        await session.commit()

        # Search Apollo
        all_orgs = await apollo_service.search_organizations_all_pages(
            keyword_tags=keywords,
            locations=locations if locations else None,
            max_pages=min(run.budget_apollo_credits, 50),  # 1 credit per page
        )

        # Extract domains
        domains = []
        for org in all_orgs:
            domain = org.get("primary_domain") or org.get("website_url", "")
            if domain:
                domain = domain.replace("https://", "").replace("http://", "").strip("/")
                if domain and "." in domain:
                    domains.append(domain)

        domains = list(set(domains))
        job.domains_found = len(domains)
        await session.commit()

        if not domains:
            job.status = SearchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await session.commit()
            return 0

        # Exclude domains already in CRM
        crm_domains = await self._get_crm_domains(session, run.company_id)
        domains = [d for d in domains if d not in crm_domains]

        logger.info(f"[TAM] Apollo: {job.domains_found} raw → {len(domains)} after CRM dedup ({len(crm_domains)} CRM domains excluded)")

        if not domains:
            job.status = SearchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await session.commit()
            return 0

        # Scrape + analyze with cluster-specific target_segments
        # _scrape_and_analyze_domains handles dedup, Crona/httpx scraping, GPT analysis
        await company_search_service._scrape_and_analyze_domains(
            session, job, domains[:500], target_segments
        )

        # Count targets
        target_count_result = await session.execute(
            select(func.count()).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
            )
        )
        target_count = target_count_result.scalar() or 0

        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await session.commit()

        logger.info(f"[TAM] Apollo: {len(domains)} domains → {target_count} targets")
        return target_count

    async def _run_yandex_phase(
        self,
        session: AsyncSession,
        run: LookalikeRun,
        cluster: LookalikeCluster,
        strategy: Dict[str, Any],
        target_segments: str,
    ) -> int:
        """Create Yandex search job with cluster queries → run → analyze."""
        from app.services.search_service import search_service

        queries = strategy.get("yandex_queries", [])[:run.budget_yandex_queries]

        # Create SearchJob
        job = SearchJob(
            company_id=run.company_id,
            project_id=run.project_id,
            cluster_id=cluster.id,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=len(queries),
            config={"cluster_id": cluster.id, "target_segments_override": target_segments},
        )
        session.add(job)
        await session.flush()
        run.yandex_job_id = job.id

        # Add queries
        for q_text in queries:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=q_text,
                status=SearchQueryStatus.PENDING,
            )
            session.add(sq)

        await session.commit()

        # Run search job (handles scraping internally)
        await search_service.run_search_job(session, job.id)

        # Now analyze the found domains with cluster-specific scoring
        # Reload job to get updated domain counts
        await session.refresh(job)

        # Get unanalyzed domains from this job
        domains_result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.search_job_id == job.id,
                SearchResult.analyzed_at.is_(None),
            )
        )
        unanalyzed_domains = [r[0] for r in domains_result.fetchall()]

        if unanalyzed_domains:
            await company_search_service._scrape_and_analyze_domains(
                session, job, unanalyzed_domains, target_segments
            )

        # Count targets
        target_count_result = await session.execute(
            select(func.count()).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
            )
        )
        target_count = target_count_result.scalar() or 0

        logger.info(f"[TAM] Yandex: {len(queries)} queries → {target_count} targets")
        return target_count

    async def _run_google_phase(
        self,
        session: AsyncSession,
        run: LookalikeRun,
        cluster: LookalikeCluster,
        strategy: Dict[str, Any],
        target_segments: str,
    ) -> int:
        """Same as Yandex but with Google SERP."""
        from app.services.search_service import search_service

        queries = strategy.get("google_queries", [])[:run.budget_google_queries]

        job = SearchJob(
            company_id=run.company_id,
            project_id=run.project_id,
            cluster_id=cluster.id,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.GOOGLE_SERP,
            queries_total=len(queries),
            config={"cluster_id": cluster.id, "target_segments_override": target_segments},
        )
        session.add(job)
        await session.flush()
        run.google_job_id = job.id

        for q_text in queries:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=q_text,
                status=SearchQueryStatus.PENDING,
            )
            session.add(sq)

        await session.commit()

        await search_service.run_search_job(session, job.id)
        await session.refresh(job)

        domains_result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.search_job_id == job.id,
                SearchResult.analyzed_at.is_(None),
            )
        )
        unanalyzed_domains = [r[0] for r in domains_result.fetchall()]

        if unanalyzed_domains:
            await company_search_service._scrape_and_analyze_domains(
                session, job, unanalyzed_domains, target_segments
            )

        target_count_result = await session.execute(
            select(func.count()).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
            )
        )
        target_count = target_count_result.scalar() or 0

        logger.info(f"[TAM] Google: {len(queries)} queries → {target_count} targets")
        return target_count

    async def _get_crm_domains(self, session: AsyncSession, company_id: int) -> set:
        """Get all domains already in CRM + SmartLead to exclude from search."""
        # CRM contacts
        result = await session.execute(
            select(Contact.domain).where(
                Contact.company_id == company_id,
                Contact.domain.isnot(None),
                Contact.deleted_at.is_(None),
            ).distinct()
        )
        domains = {r[0] for r in result.fetchall()}

        # Also exclude domains from SmartLead processed replies (already contacted)
        try:
            sl_result = await session.execute(
                select(func.distinct(func.split_part(ProcessedReply.lead_email, '@', 2))).where(
                    ProcessedReply.lead_email.isnot(None),
                )
            )
            sl_domains = {r[0] for r in sl_result.fetchall() if r[0] and '.' in r[0]}
            domains.update(sl_domains)
        except Exception as e:
            logger.warning(f"[TAM] Failed to load SmartLead domains for dedup: {e}")

        logger.info(f"[TAM] CRM+SmartLead dedup: {len(domains)} total domains to exclude")
        return domains

    # ------------------------------------------------------------------ #
    # Dashboard / Stats
    # ------------------------------------------------------------------ #

    async def get_project_dashboard(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> Dict[str, Any]:
        """KPI dashboard for a project's TAM analysis."""
        # Get clusters
        result = await session.execute(
            select(LookalikeCluster).where(
                LookalikeCluster.project_id == project_id,
                LookalikeCluster.is_active == True,
            )
        )
        clusters = list(result.scalars().all())

        cluster_stats = []
        total_leads = 0
        total_lookalikes = 0

        for c in clusters:
            stats = {
                "id": c.id,
                "name": c.name,
                "business_model": c.business_model,
                "offer_fit": c.offer_fit,
                "qualified_leads": c.qualified_lead_count or 0,
                "apollo_found": c.apollo_companies_found or 0,
                "yandex_found": c.yandex_targets_found or 0,
                "google_found": c.google_targets_found or 0,
                "total_lookalikes": c.total_lookalikes or 0,
                "has_strategy": bool(c.search_strategy),
            }
            cluster_stats.append(stats)
            total_leads += stats["qualified_leads"]
            total_lookalikes += stats["total_lookalikes"]

        return {
            "project_id": project_id,
            "total_clusters": len(clusters),
            "total_qualified_leads": total_leads,
            "total_lookalikes": total_lookalikes,
            "clusters": cluster_stats,
        }


lookalike_service = LookalikeService()
