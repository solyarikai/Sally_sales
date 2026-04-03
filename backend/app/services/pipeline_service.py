"""
Pipeline Service — Orchestrator for the outreach data processing pipeline.

Manages the flow: SearchResults → DiscoveredCompany → Contact Extraction → Apollo Enrichment → CRM Promotion.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import SearchJob, SearchResult
from app.models.pipeline import (
    DiscoveredCompany, DiscoveredCompanyStatus,
    ExtractedContact, ContactSource,
    PipelineEvent, PipelineEventType,
    EnrichmentAttempt,
)
from app.models.contact import Contact, Project
from app.services.contact_extraction_service import contact_extraction_service
from app.services.apollo_service import apollo_service
from app.services.enrichment_intelligence_service import enrichment_intelligence_service

logger = logging.getLogger(__name__)


class PipelineService:
    """Orchestrates the full outreach pipeline."""

    # ========== Promote Search Results → DiscoveredCompany ==========

    async def promote_search_results(
        self,
        session: AsyncSession,
        search_job_id: int,
    ) -> int:
        """
        Create DiscoveredCompany records from SearchResults.
        Upserts by (company_id, project_id, domain).
        Returns count of newly created records.
        """
        # Load job
        job_result = await session.execute(
            select(SearchJob).where(SearchJob.id == search_job_id)
        )
        job = job_result.scalar_one_or_none()
        if not job:
            logger.error(f"SearchJob {search_job_id} not found")
            return 0

        # Load results
        results_q = await session.execute(
            select(SearchResult).where(SearchResult.search_job_id == search_job_id)
        )
        results = results_q.scalars().all()

        if not results:
            logger.info(f"No results to promote for job {search_job_id}")
            return 0

        created_count = 0
        for sr in results:
            # Check if already exists
            existing = await session.execute(
                select(DiscoveredCompany).where(
                    DiscoveredCompany.company_id == job.company_id,
                    DiscoveredCompany.project_id == job.project_id,
                    DiscoveredCompany.domain == sr.domain,
                )
            )
            dc = existing.scalar_one_or_none()

            if dc:
                # Update existing with latest analysis
                dc.is_target = sr.is_target
                dc.confidence = sr.confidence
                dc.reasoning = sr.reasoning
                dc.company_info = sr.company_info
                dc.matched_segment = sr.matched_segment
                dc.status = DiscoveredCompanyStatus.ANALYZED
                dc.scraped_html = sr.html_snippet
                dc.scraped_at = sr.scraped_at
            else:
                # Create new
                company_info = sr.company_info or {}
                dc = DiscoveredCompany(
                    company_id=job.company_id,
                    project_id=job.project_id,
                    domain=sr.domain,
                    name=company_info.get("name"),
                    url=sr.url,
                    search_result_id=sr.id,
                    search_job_id=job.id,
                    is_target=sr.is_target,
                    confidence=sr.confidence,
                    reasoning=sr.reasoning,
                    company_info=sr.company_info,
                    matched_segment=sr.matched_segment,
                    status=DiscoveredCompanyStatus.ANALYZED,
                    scraped_html=sr.html_snippet,
                    scraped_at=sr.scraped_at,
                )
                session.add(dc)
                created_count += 1

            await session.flush()

            # Link back
            sr.discovered_company_id = dc.id

        # Create audit event
        event = PipelineEvent(
            company_id=job.company_id,
            event_type=PipelineEventType.SEARCH_COMPLETED,
            detail={
                "search_job_id": search_job_id,
                "results_count": len(results),
                "new_companies": created_count,
            },
        )
        session.add(event)
        await session.commit()

        logger.info(f"Promoted {created_count} new companies from job {search_job_id} ({len(results)} total results)")
        return created_count

    # ========== Contact Extraction ==========

    async def extract_contacts_batch(
        self,
        session: AsyncSession,
        discovered_company_ids: List[int],
        company_id: int,
    ) -> Dict[str, Any]:
        """
        Run GPT contact extraction on selected DiscoveredCompanies.
        Uses cached scraped_html. Proactively scrapes subpages for all targets.
        All attempts logged to enrichment_attempts.
        """
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.id.in_(discovered_company_ids),
                DiscoveredCompany.company_id == company_id,
            )
        )
        companies = result.scalars().all()

        stats = {"processed": 0, "contacts_found": 0, "errors": 0, "skipped": 0}

        for dc in companies:
            # Skip if contacts already extracted
            if dc.contacts_count and dc.contacts_count > 0:
                stats["skipped"] += 1
                continue

            html = dc.scraped_html or ""
            if not html.strip():
                # Try to scrape if no cached HTML
                from app.services.company_search_service import company_search_service
                html = await company_search_service.scrape_domain(dc.domain)
                if html:
                    dc.scraped_html = html[:50000]
                    dc.scraped_at = datetime.utcnow()

            if not html:
                # Log failed attempt
                attempt_id = await enrichment_intelligence_service.log_attempt(
                    session, dc.id, "WEBSITE_SCRAPE", "homepage_gpt",
                )
                await enrichment_intelligence_service.update_attempt(
                    session, attempt_id, "ERROR", error_message="No HTML to extract contacts from",
                )
                stats["errors"] += 1
                self._add_event(session, dc, PipelineEventType.ERROR, company_id, error_message="No HTML to extract contacts from")
                continue

            try:
                # --- Homepage extraction (logged) ---
                homepage_attempt_id = await enrichment_intelligence_service.log_attempt(
                    session, dc.id, "WEBSITE_SCRAPE", "homepage_gpt",
                )

                contacts = await contact_extraction_service.extract_contacts_from_html(dc.domain, html)

                # Regex fallback: find emails/phones GPT missed
                gpt_emails = {(c.get("email") or "").lower() for c in contacts if c.get("email")}
                gpt_phones = {(c.get("phone") or "").strip() for c in contacts if c.get("phone")}

                regex_emails = contact_extraction_service.extract_emails_regex(html)
                regex_phones = contact_extraction_service.extract_phones_regex(html)

                for re_email in regex_emails:
                    if re_email.lower() not in gpt_emails:
                        contacts.append({
                            "email": re_email.lower(),
                            "phone": None,
                            "first_name": None,
                            "last_name": None,
                            "job_title": None,
                            "confidence": 0.4,
                            "source": "regex",
                        })
                for re_phone in regex_phones:
                    if re_phone not in gpt_phones:
                        contacts.append({
                            "email": None,
                            "phone": re_phone,
                            "first_name": None,
                            "last_name": None,
                            "job_title": None,
                            "confidence": 0.4,
                            "source": "regex",
                        })

                homepage_emails = [c.get("email") for c in contacts if c.get("email")]
                await enrichment_intelligence_service.update_attempt(
                    session, homepage_attempt_id,
                    status="SUCCESS" if contacts else "ZERO_RESULTS",
                    contacts_found=len(contacts),
                    emails_found=len(homepage_emails),
                    result_summary={"emails": homepage_emails[:20]},
                )

                # --- Proactive subpage scraping for ALL targets (not just fallback) ---
                subpage_contacts = await self._scrape_subpages_for_contacts(
                    dc.domain, session=session, dc_id=dc.id,
                )
                if subpage_contacts:
                    existing_emails = {(c.get("email") or "").lower() for c in contacts if c.get("email")}
                    for sc in subpage_contacts:
                        sc_email = (sc.get("email") or "").lower()
                        if sc_email and sc_email not in existing_emails:
                            contacts.append(sc)
                            existing_emails.add(sc_email)
                        elif not sc_email and sc.get("phone"):
                            contacts.append(sc)

                # Store contacts (with email validation)
                from app.services.contact_extraction_service import is_valid_email
                emails = []
                phones = []
                for c_data in contacts:
                    email = c_data.get("email")
                    # Skip contacts with invalid/junk emails
                    if email and not is_valid_email(email):
                        logger.debug(f"Rejected junk email: {email} from {dc.domain}")
                        continue

                    source = ContactSource.WEBSITE_SCRAPE
                    if c_data.get("source") in ("subpage_regex", "subpage_gpt"):
                        source = ContactSource.SUBPAGE_SCRAPE

                    ec = ExtractedContact(
                        discovered_company_id=dc.id,
                        email=email,
                        phone=c_data.get("phone"),
                        first_name=c_data.get("first_name"),
                        last_name=c_data.get("last_name"),
                        job_title=c_data.get("job_title"),
                        source=source,
                        raw_data=c_data,
                    )
                    session.add(ec)

                    if email:
                        emails.append(email)
                    if c_data.get("phone"):
                        phones.append(c_data["phone"])

                if len(contacts) > 0:
                    dc.contacts_count = len(contacts)
                    dc.emails_found = emails
                    dc.phones_found = phones
                    if dc.status in (DiscoveredCompanyStatus.NEW, DiscoveredCompanyStatus.SCRAPED, DiscoveredCompanyStatus.ANALYZED):
                        dc.status = DiscoveredCompanyStatus.CONTACTS_EXTRACTED

                stats["contacts_found"] += len(contacts)
                stats["processed"] += 1

                self._add_event(session, dc, PipelineEventType.CONTACT_EXTRACTED, company_id, detail={
                    "contacts_found": len(contacts),
                    "emails": emails,
                })

            except Exception as e:
                logger.error(f"Contact extraction failed for {dc.domain}: {e}")
                stats["errors"] += 1
                self._add_event(session, dc, PipelineEventType.ERROR, company_id, error_message=str(e))

        await session.commit()
        return stats

    # ========== Subpage Scraping Fallback ==========

    CONTACT_SUBPAGES = ["/contacts", "/contact", "/kontakty", "/about"]

    async def _scrape_subpages_for_contacts(
        self,
        domain: str,
        session: Optional[AsyncSession] = None,
        dc_id: Optional[int] = None,
    ) -> list[dict]:
        """
        Proactively scrape /contacts, /about subpages for all targets.
        Each subpage attempt is logged to enrichment_attempts when session is provided.
        Returns list of contact dicts (aggregated from all subpages that yield contacts).
        """
        from app.services.crona_service import crona_service
        import httpx as _httpx

        all_contacts = []
        seen_emails: set[str] = set()

        for subpath in self.CONTACT_SUBPAGES:
            url = f"https://{domain}{subpath}"
            attempt_id = None

            # Log attempt start
            if session and dc_id:
                attempt_id = await enrichment_intelligence_service.log_attempt(
                    session, dc_id, "SUBPAGE_SCRAPE", f"subpage_{subpath}",
                    config={"subpage_path": subpath, "url": url},
                )

            try:
                text = None
                # Try Crona first, fall back to httpx
                if crona_service.is_configured:
                    results = await crona_service.scrape_domains([url])
                    for v in results.values():
                        if v and len(v.strip()) > 50:
                            text = v
                            break

                if not text:
                    # httpx fallback
                    try:
                        async with _httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                            resp = await client.get(url)
                            if resp.status_code == 200 and len(resp.text) > 100:
                                text = resp.text
                    except Exception:
                        pass

                if not text:
                    if session and attempt_id:
                        await enrichment_intelligence_service.update_attempt(
                            session, attempt_id, "ZERO_RESULTS",
                        )
                    continue

                contacts = await contact_extraction_service.extract_contacts_from_html(domain, text)
                # Mark source for subpage contacts
                for c in contacts:
                    c["source"] = "subpage_gpt"

                # Also try regex
                regex_emails = contact_extraction_service.extract_emails_regex(text)
                existing = {(c.get("email") or "").lower() for c in contacts}
                for em in regex_emails:
                    if em.lower() not in existing:
                        contacts.append({
                            "email": em.lower(), "phone": None,
                            "first_name": None, "last_name": None,
                            "job_title": None, "confidence": 0.4,
                            "source": "subpage_regex",
                        })

                # Deduplicate against already-found contacts
                new_contacts = []
                for c in contacts:
                    c_email = (c.get("email") or "").lower()
                    if c_email and c_email not in seen_emails:
                        new_contacts.append(c)
                        seen_emails.add(c_email)
                    elif not c_email and c.get("phone"):
                        new_contacts.append(c)

                subpage_emails = [c.get("email") for c in new_contacts if c.get("email")]

                if session and attempt_id:
                    await enrichment_intelligence_service.update_attempt(
                        session, attempt_id,
                        status="SUCCESS" if new_contacts else "ZERO_RESULTS",
                        contacts_found=len(new_contacts),
                        emails_found=len(subpage_emails),
                        result_summary={"emails": subpage_emails[:20], "subpage": subpath},
                    )

                if new_contacts:
                    logger.info(f"Subpage {subpath} found {len(new_contacts)} contacts for {domain}")
                    all_contacts.extend(new_contacts)

            except Exception as e:
                logger.debug(f"Subpage scrape {domain}{subpath} failed: {e}")
                if session and attempt_id:
                    await enrichment_intelligence_service.update_attempt(
                        session, attempt_id, "ERROR",
                        error_message=str(e)[:500],
                    )
                continue

        return all_contacts

    # ========== Apollo Enrichment ==========

    async def enrich_apollo_batch(
        self,
        session: AsyncSession,
        discovered_company_ids: List[int],
        company_id: int,
        max_people: int = 5,
        max_credits: Optional[int] = None,
        titles: Optional[List[str]] = None,
        force_retry: bool = False,
    ) -> Dict[str, Any]:
        """Run Apollo enrichment on selected DiscoveredCompanies.

        With force_retry=False (default), skips companies with a recent successful Apollo attempt.
        With force_retry=True, re-enriches even previously-enriched companies.
        All attempts logged to enrichment_attempts.
        """
        if not apollo_service.is_configured():
            return {"error": "Apollo API key not configured", "processed": 0}

        if force_retry:
            # Load all requested companies regardless of enrichment status
            result = await session.execute(
                select(DiscoveredCompany).where(
                    DiscoveredCompany.id.in_(discovered_company_ids),
                    DiscoveredCompany.company_id == company_id,
                )
            )
            companies = result.scalars().all()
            # Filter out only those with a recent successful Apollo attempt (30 days)
            filtered = []
            for dc in companies:
                has_recent = await enrichment_intelligence_service.has_recent_success(
                    session, dc.id, "APOLLO_PEOPLE", days=30,
                )
                if not has_recent:
                    filtered.append(dc)
            skipped_count = len(discovered_company_ids) - len(filtered)
            companies = filtered
        else:
            # Legacy behavior: skip already-enriched
            result = await session.execute(
                select(DiscoveredCompany).where(
                    DiscoveredCompany.id.in_(discovered_company_ids),
                    DiscoveredCompany.company_id == company_id,
                    DiscoveredCompany.apollo_enriched_at.is_(None),
                )
            )
            companies = result.scalars().all()
            skipped_count = len(discovered_company_ids) - len(companies)

        stats = {"processed": 0, "people_found": 0, "errors": 0, "credits_used": 0, "skipped": skipped_count}

        # Snapshot credits BEFORE this batch — return delta, not cumulative
        credits_before = apollo_service.credits_used

        for dc in companies:
            # Credit budget check uses batch delta, not cumulative total
            batch_credits = apollo_service.credits_used - credits_before
            if max_credits is not None and batch_credits >= max_credits:
                logger.info(f"Apollo credit cap reached ({max_credits}), stopping enrichment. Batch used {batch_credits} credits.")
                stats["paused_for_budget"] = True
                break

            credits_before_company = apollo_service.credits_used

            # Free org enrichment — get company classification data before spending credits
            if not dc.apollo_org_data:
                try:
                    org_data = await apollo_service.enrich_organization(dc.domain)
                    if org_data:
                        dc.apollo_org_data = {
                            "name": org_data.get("name"),
                            "industry": org_data.get("industry"),
                            "keywords": org_data.get("keywords", []),
                            "estimated_num_employees": org_data.get("estimated_num_employees"),
                            "annual_revenue": org_data.get("annual_revenue"),
                            "annual_revenue_printed": org_data.get("annual_revenue_printed"),
                            "founded_year": org_data.get("founded_year"),
                            "linkedin_url": org_data.get("linkedin_url"),
                            "website_url": org_data.get("website_url"),
                            "country": org_data.get("country"),
                            "city": org_data.get("city"),
                            "state": org_data.get("state"),
                            "languages": org_data.get("languages", []),
                            "technologies": org_data.get("technologies", []),
                            "phone": org_data.get("phone"),
                            "primary_domain": org_data.get("primary_domain"),
                            "logo_url": org_data.get("logo_url"),
                            "raw_address": org_data.get("raw_address"),
                            "seo_description": org_data.get("seo_description"),
                            "short_description": org_data.get("short_description"),
                            "suborganizations": [
                                {"name": s.get("name"), "domain": s.get("website_url")}
                                for s in (org_data.get("suborganizations") or [])[:10]
                            ],
                            "num_suborganizations": org_data.get("num_suborganizations"),
                            "departmental_head_count": org_data.get("departmental_head_count"),
                        }
                        logger.info(f"Apollo org enrichment for {dc.domain}: industry={org_data.get('industry')}, employees={org_data.get('estimated_num_employees')}")
                except Exception as e:
                    logger.warning(f"Apollo org enrichment failed for {dc.domain}: {e}")

            # Log attempt
            attempt_id = await enrichment_intelligence_service.log_attempt(
                session, dc.id, "APOLLO_PEOPLE",
                method=f"apollo_titles_{'_'.join(titles[:3])}" if titles else "apollo_default",
                config={"max_people": max_people, "titles": titles, "force_retry": force_retry},
            )

            search_context = {
                "titles": titles,
                "max_people": max_people,
                "domain": dc.domain,
                "force_retry": force_retry,
            }

            try:
                people = await apollo_service.enrich_by_domain(dc.domain, limit=max_people, titles=titles)

                credits_for_company = apollo_service.credits_used - credits_before_company
                people_emails = [p.get("email") for p in people if p.get("email")]

                # Update attempt
                await enrichment_intelligence_service.update_attempt(
                    session, attempt_id,
                    status="SUCCESS" if people else "ZERO_RESULTS",
                    contacts_found=len(people),
                    emails_found=len(people_emails),
                    credits_used=credits_for_company,
                    result_summary={"emails": people_emails[:20], "domain": dc.domain},
                )

                for person in people:
                    ec = ExtractedContact(
                        discovered_company_id=dc.id,
                        email=person.get("email"),
                        phone=person.get("phone"),
                        first_name=person.get("first_name"),
                        last_name=person.get("last_name"),
                        job_title=person.get("job_title"),
                        linkedin_url=person.get("linkedin_url"),
                        source=ContactSource.APOLLO,
                        is_verified=person.get("is_verified", False),
                        verification_method="apollo" if person.get("is_verified") else None,
                        raw_data=person.get("raw_data"),
                        apollo_search_context=search_context,
                    )
                    session.add(ec)

                dc.apollo_people_count = (dc.apollo_people_count or 0) + len(people) if force_retry else len(people)
                dc.apollo_enriched_at = datetime.utcnow()
                dc.apollo_credits_used = (dc.apollo_credits_used or 0) + credits_for_company
                dc.contacts_count = (dc.contacts_count or 0) + len(people)
                if dc.status in (DiscoveredCompanyStatus.NEW, DiscoveredCompanyStatus.SCRAPED, DiscoveredCompanyStatus.ANALYZED, DiscoveredCompanyStatus.CONTACTS_EXTRACTED):
                    dc.status = DiscoveredCompanyStatus.ENRICHED

                stats["processed"] += 1
                stats["people_found"] += len(people)

                self._add_event(session, dc, PipelineEventType.APOLLO_ENRICHED, company_id, detail={
                    "people_found": len(people),
                    "credits_used": credits_for_company,
                    "domain": dc.domain,
                    "force_retry": force_retry,
                })

                logger.info(f"Apollo enriched {dc.domain}: {len(people)} people, {credits_for_company} credits")

            except Exception as e:
                logger.error(f"Apollo enrichment failed for {dc.domain}: {e}")
                await enrichment_intelligence_service.update_attempt(
                    session, attempt_id, "ERROR",
                    error_message=str(e)[:500],
                )
                stats["errors"] += 1
                self._add_event(session, dc, PipelineEventType.ERROR, company_id, error_message=str(e))

        # Return BATCH DELTA — not cumulative total
        stats["credits_used"] = apollo_service.credits_used - credits_before
        await session.commit()
        return stats

    # ========== Promote to CRM ==========

    async def promote_to_crm(
        self,
        session: AsyncSession,
        extracted_contact_ids: List[int],
        company_id: int,
        project_id: Optional[int] = None,
        segment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Promote ExtractedContacts to CRM Contact records with full provenance."""
        result = await session.execute(
            select(ExtractedContact)
            .join(DiscoveredCompany)
            .where(
                ExtractedContact.id.in_(extracted_contact_ids),
                DiscoveredCompany.company_id == company_id,
            )
        )
        extracted = result.scalars().all()

        stats = {"promoted": 0, "skipped": 0, "errors": 0}

        for ec in extracted:
            if ec.contact_id:
                stats["skipped"] += 1
                continue

            if not ec.email:
                stats["skipped"] += 1
                continue

            # Check if contact already exists by email
            existing = await session.execute(
                select(Contact).where(
                    Contact.email == ec.email,
                    Contact.company_id == company_id,
                )
            )
            existing_contact = existing.scalar_one_or_none()

            if existing_contact:
                ec.contact_id = existing_contact.id
                stats["skipped"] += 1
                continue

            # Load parent company info + search provenance
            dc_result = await session.execute(
                select(DiscoveredCompany).where(DiscoveredCompany.id == ec.discovered_company_id)
            )
            dc = dc_result.scalar_one_or_none()

            # Build gathering_details with full provenance chain
            gathering_details = self._build_gathering_details(session, ec, dc)
            if dc and dc.search_result_id:
                # Enrich with search query provenance
                from sqlalchemy import text as sql_text
                prov_row = await session.execute(sql_text("""
                    SELECT sq.query_text, sq.geo, sq.search_engine,
                           sj.id as search_job_id, sr.matched_segment
                    FROM search_results sr
                    LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
                    LEFT JOIN search_jobs sj ON sq.search_job_id = sj.id
                    WHERE sr.id = :sr_id
                    LIMIT 1
                """), {"sr_id": dc.search_result_id})
                prov = prov_row.fetchone()
                if prov:
                    if prov.search_job_id:
                        gathering_details["search_job_id"] = prov.search_job_id
                    if prov.query_text:
                        gathering_details["query"] = prov.query_text
                    if prov.geo:
                        gathering_details["geo"] = prov.geo
                    if prov.search_engine:
                        gathering_details["search_engine"] = str(prov.search_engine)
                    if prov.matched_segment:
                        gathering_details["segment"] = prov.matched_segment

            source_str = "pipeline"
            if ec.source == ContactSource.APOLLO:
                source_str = "apollo"
            elif ec.source == ContactSource.SUBPAGE_SCRAPE:
                source_str = "subpage_scrape"

            # Resolve segment: explicit > search_result > discovered_company
            resolved_segment = segment or gathering_details.get("segment") or (dc.matched_segment if dc else None)

            contact = Contact(
                company_id=company_id,
                email=ec.email,
                first_name=ec.first_name,
                last_name=ec.last_name,
                company_name=dc.name if dc else None,
                domain=dc.domain if dc else None,
                job_title=ec.job_title,
                phone=ec.phone,
                linkedin_url=ec.linkedin_url,
                segment=resolved_segment,
                project_id=project_id,
                source=source_str,
                status="lead",
                provenance=gathering_details,
                email_verification_result='valid' if ec.is_verified else None,
            )
            session.add(contact)
            await session.flush()

            ec.contact_id = contact.id
            stats["promoted"] += 1

            if dc:
                self._add_event(session, dc, PipelineEventType.PROMOTED_TO_CRM, company_id, detail={
                    "contact_id": contact.id,
                    "email": ec.email,
                })

        await session.commit()
        return stats

    def _build_gathering_details(
        self,
        session: AsyncSession,
        ec: ExtractedContact,
        dc: Optional[DiscoveredCompany],
    ) -> Dict[str, Any]:
        """Build provenance JSON for a promoted contact."""
        details: Dict[str, Any] = {
            "gathered_at": datetime.utcnow().isoformat(),
            "source": str(ec.source.value) if ec.source else "unknown",
            "extracted_contact_id": ec.id,
        }
        if dc:
            details["domain"] = dc.domain
            details["company_name"] = dc.name
            details["discovered_company_id"] = dc.id
            if dc.confidence is not None:
                details["confidence"] = dc.confidence
            if dc.search_job_id:
                details["search_job_id"] = dc.search_job_id
        return details

    # ========== Email Verification ==========

    async def verify_emails_batch(
        self,
        session: AsyncSession,
        extracted_contact_ids: List[int],
        company_id: int,
        project_id: Optional[int] = None,
        max_credits: int = 100,
    ) -> Dict[str, Any]:
        """Verify emails for extracted contacts via Findymail.

        Only works if findymail is enabled in project's auto_enrich_config.
        """
        # Check if findymail is enabled for this project
        if project_id:
            proj_result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = proj_result.scalar_one_or_none()
            if project:
                config = project.auto_enrich_config or {}
                if not config.get("findymail_enabled", False):
                    return {"error": "Findymail is disabled for this project. Enable it first.", "verified": 0}

        from app.services.email_verification_service import email_verification_service

        # Load contacts
        result = await session.execute(
            select(ExtractedContact)
            .join(DiscoveredCompany)
            .where(
                ExtractedContact.id.in_(extracted_contact_ids),
                DiscoveredCompany.company_id == company_id,
                ExtractedContact.email.isnot(None),
            )
        )
        contacts = result.scalars().all()

        emails = [ec.email for ec in contacts if ec.email]
        email_to_extracted = {ec.email: ec.id for ec in contacts if ec.email}
        email_to_contact = {ec.email: ec.contact_id for ec in contacts if ec.email and ec.contact_id}

        batch_result = await email_verification_service.verify_batch(
            session, emails,
            project_id=project_id,
            company_id=company_id,
            max_credits=max_credits,
            email_to_contact=email_to_contact,
            email_to_extracted=email_to_extracted,
        )

        await session.commit()
        return batch_result.get("stats", {})

    # ========== Pipeline Stats ==========

    async def get_pipeline_stats(
        self,
        session: AsyncSession,
        company_id: int,
        project_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Aggregate pipeline stats."""
        base_filter = [DiscoveredCompany.company_id == company_id]
        if project_id:
            base_filter.append(DiscoveredCompany.project_id == project_id)

        # Total
        total_q = await session.execute(
            select(func.count()).select_from(DiscoveredCompany).where(*base_filter)
        )
        total = total_q.scalar() or 0

        # By status
        status_q = await session.execute(
            select(DiscoveredCompany.status, func.count())
            .where(*base_filter)
            .group_by(DiscoveredCompany.status)
        )
        status_counts = dict(status_q.fetchall())

        # Targets
        targets_q = await session.execute(
            select(func.count()).select_from(DiscoveredCompany)
            .where(*base_filter, DiscoveredCompany.is_target == True)
        )
        targets = targets_q.scalar() or 0

        # Targets already in campaigns (domain exists in contacts table)
        campaign_domains_subq = (
            select(func.lower(Contact.domain))
            .where(Contact.domain.isnot(None), Contact.domain != "")
            .distinct()
            .scalar_subquery()
        )
        targets_in_campaigns_q = await session.execute(
            select(func.count()).select_from(DiscoveredCompany)
            .where(
                *base_filter,
                DiscoveredCompany.is_target == True,
                func.lower(DiscoveredCompany.domain).in_(campaign_domains_subq),
            )
        )
        targets_in_campaigns = targets_in_campaigns_q.scalar() or 0
        targets_new = targets - targets_in_campaigns

        # Total extracted contacts
        contacts_q = await session.execute(
            select(func.sum(DiscoveredCompany.contacts_count))
            .where(*base_filter)
        )
        total_contacts = contacts_q.scalar() or 0

        # Apollo people
        apollo_q = await session.execute(
            select(func.sum(DiscoveredCompany.apollo_people_count))
            .where(*base_filter)
        )
        total_apollo = apollo_q.scalar() or 0

        # Contact breakdown by source
        dc_ids_subq = select(DiscoveredCompany.id).where(*base_filter).scalar_subquery()
        contact_stats_q = await session.execute(
            select(
                ExtractedContact.source,
                func.count().label("total"),
                func.count().filter(ExtractedContact.email.isnot(None)).label("with_email"),
                func.count().filter(ExtractedContact.linkedin_url.isnot(None)).label("with_linkedin"),
                func.count().filter(ExtractedContact.phone.isnot(None)).label("with_phone"),
            )
            .where(ExtractedContact.discovered_company_id.in_(dc_ids_subq))
            .group_by(ExtractedContact.source)
        )
        contact_by_source = {}
        for row in contact_stats_q.fetchall():
            contact_by_source[row.source] = {
                "total": row.total, "with_email": row.with_email,
                "with_linkedin": row.with_linkedin, "with_phone": row.with_phone,
            }
        apollo_cs = contact_by_source.get(ContactSource.APOLLO, {})
        website_cs = contact_by_source.get(ContactSource.WEBSITE_SCRAPE, {})

        return {
            "total_discovered": total,
            "targets": targets,
            "targets_new": targets_new,
            "targets_in_campaigns": targets_in_campaigns,
            "contacts_extracted": status_counts.get(DiscoveredCompanyStatus.CONTACTS_EXTRACTED, 0) + status_counts.get(DiscoveredCompanyStatus.ENRICHED, 0) + status_counts.get(DiscoveredCompanyStatus.EXPORTED, 0),
            "enriched": status_counts.get(DiscoveredCompanyStatus.ENRICHED, 0) + status_counts.get(DiscoveredCompanyStatus.EXPORTED, 0),
            "exported": status_counts.get(DiscoveredCompanyStatus.EXPORTED, 0),
            "rejected": status_counts.get(DiscoveredCompanyStatus.REJECTED, 0),
            "total_contacts": total_contacts,
            "total_apollo_people": total_apollo,
            "apollo_contacts": apollo_cs.get("total", 0),
            "apollo_with_email": apollo_cs.get("with_email", 0),
            "apollo_with_linkedin": apollo_cs.get("with_linkedin", 0),
            "website_contacts": website_cs.get("total", 0),
            "website_with_email": website_cs.get("with_email", 0),
            "website_with_phone": website_cs.get("with_phone", 0),
        }

    # ========== List / Get ==========

    # Allowed sort columns (whitelist to prevent SQL injection)
    SORT_COLUMNS = {
        "domain": DiscoveredCompany.domain,
        "name": DiscoveredCompany.name,
        "status": DiscoveredCompany.status,
        "is_target": DiscoveredCompany.is_target,
        "confidence": DiscoveredCompany.confidence,
        "contacts_count": DiscoveredCompany.contacts_count,
        "apollo_people_count": DiscoveredCompany.apollo_people_count,
        "created_at": DiscoveredCompany.created_at,
    }

    async def list_discovered_companies(
        self,
        session: AsyncSession,
        company_id: int,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        is_target: Optional[bool] = None,
        search: Optional[str] = None,
        search_job_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """List discovered companies with filters."""
        filters = [DiscoveredCompany.company_id == company_id]
        if project_id:
            filters.append(DiscoveredCompany.project_id == project_id)
        if status:
            filters.append(DiscoveredCompany.status == status)
        if is_target is not None:
            filters.append(DiscoveredCompany.is_target == is_target)
        if search:
            filters.append(
                (DiscoveredCompany.domain.ilike(f"%{search}%")) |
                (DiscoveredCompany.name.ilike(f"%{search}%"))
            )
        if search_job_id is not None:
            filters.append(DiscoveredCompany.search_job_id == search_job_id)

        # Count
        count_q = await session.execute(
            select(func.count()).select_from(DiscoveredCompany).where(*filters)
        )
        total = count_q.scalar() or 0

        # Build order_by
        order_clauses = []
        if sort_by and sort_by in self.SORT_COLUMNS:
            col = self.SORT_COLUMNS[sort_by]
            order_clauses.append(col.asc() if sort_order == "asc" else col.desc())
        else:
            order_clauses = [
                DiscoveredCompany.is_target.desc(),
                DiscoveredCompany.confidence.desc(),
                DiscoveredCompany.created_at.desc(),
            ]

        # Fetch
        result = await session.execute(
            select(DiscoveredCompany)
            .where(*filters)
            .order_by(*order_clauses)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_discovered_company_detail(
        self,
        session: AsyncSession,
        company_id: int,
        discovered_company_id: int,
    ) -> Optional[DiscoveredCompany]:
        """Get discovered company with contacts and events."""
        result = await session.execute(
            select(DiscoveredCompany)
            .options(
                selectinload(DiscoveredCompany.extracted_contacts),
                selectinload(DiscoveredCompany.events),
            )
            .where(
                DiscoveredCompany.id == discovered_company_id,
                DiscoveredCompany.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    # ========== Helpers ==========

    def _add_event(
        self,
        session: AsyncSession,
        dc: Optional[DiscoveredCompany],
        event_type: PipelineEventType,
        company_id: int,
        detail: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ):
        event = PipelineEvent(
            discovered_company_id=dc.id if dc else None,
            company_id=company_id,
            event_type=event_type,
            detail=detail,
            error_message=error_message,
        )
        session.add(event)


# Module-level singleton
pipeline_service = PipelineService()
