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
)
from app.models.contact import Contact, Project
from app.services.contact_extraction_service import contact_extraction_service
from app.services.apollo_service import apollo_service

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
        Uses cached scraped_html.
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
                stats["errors"] += 1
                self._add_event(session, dc, PipelineEventType.ERROR, company_id, error_message="No HTML to extract contacts from")
                continue

            try:
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

                # Store contacts
                emails = []
                phones = []
                for c_data in contacts:
                    ec = ExtractedContact(
                        discovered_company_id=dc.id,
                        email=c_data.get("email"),
                        phone=c_data.get("phone"),
                        first_name=c_data.get("first_name"),
                        last_name=c_data.get("last_name"),
                        job_title=c_data.get("job_title"),
                        source=ContactSource.WEBSITE_SCRAPE,
                        raw_data=c_data,
                    )
                    session.add(ec)

                    if c_data.get("email"):
                        emails.append(c_data["email"])
                    if c_data.get("phone"):
                        phones.append(c_data["phone"])

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

    # ========== Apollo Enrichment ==========

    async def enrich_apollo_batch(
        self,
        session: AsyncSession,
        discovered_company_ids: List[int],
        company_id: int,
        max_people: int = 5,
        max_credits: Optional[int] = None,
        titles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run Apollo enrichment on selected DiscoveredCompanies."""
        if not apollo_service.is_configured():
            return {"error": "Apollo API key not configured", "processed": 0}

        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.id.in_(discovered_company_ids),
                DiscoveredCompany.company_id == company_id,
            )
        )
        companies = result.scalars().all()

        stats = {"processed": 0, "people_found": 0, "errors": 0, "credits_used": 0, "skipped": 0}

        for dc in companies:
            # Skip if already Apollo-enriched
            if dc.apollo_enriched_at is not None:
                stats["skipped"] += 1
                continue

            if max_credits is not None and apollo_service.credits_used >= max_credits:
                logger.info(f"Apollo credit cap reached ({max_credits}), stopping enrichment")
                break

            try:
                people = await apollo_service.enrich_by_domain(dc.domain, limit=max_people, titles=titles)

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
                    )
                    session.add(ec)

                dc.apollo_people_count = len(people)
                dc.apollo_enriched_at = datetime.utcnow()
                dc.contacts_count = (dc.contacts_count or 0) + len(people)
                if dc.status in (DiscoveredCompanyStatus.NEW, DiscoveredCompanyStatus.SCRAPED, DiscoveredCompanyStatus.ANALYZED, DiscoveredCompanyStatus.CONTACTS_EXTRACTED):
                    dc.status = DiscoveredCompanyStatus.ENRICHED

                stats["processed"] += 1
                stats["people_found"] += len(people)

                self._add_event(session, dc, PipelineEventType.APOLLO_ENRICHED, company_id, detail={
                    "people_found": len(people),
                    "domain": dc.domain,
                })

            except Exception as e:
                logger.error(f"Apollo enrichment failed for {dc.domain}: {e}")
                stats["errors"] += 1
                self._add_event(session, dc, PipelineEventType.ERROR, company_id, error_message=str(e))

        stats["credits_used"] = apollo_service.credits_used
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
        """Promote ExtractedContacts to CRM Contact records."""
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

            # Load parent company info
            dc_result = await session.execute(
                select(DiscoveredCompany).where(DiscoveredCompany.id == ec.discovered_company_id)
            )
            dc = dc_result.scalar_one_or_none()

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
                segment=segment,
                project_id=project_id,
                source="pipeline" if ec.source == ContactSource.WEBSITE_SCRAPE else "apollo",
                status="lead",
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

    async def list_discovered_companies(
        self,
        session: AsyncSession,
        company_id: int,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        is_target: Optional[bool] = None,
        search: Optional[str] = None,
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

        # Count
        count_q = await session.execute(
            select(func.count()).select_from(DiscoveredCompany).where(*filters)
        )
        total = count_q.scalar() or 0

        # Fetch
        result = await session.execute(
            select(DiscoveredCompany)
            .where(*filters)
            .order_by(
                DiscoveredCompany.is_target.desc(),
                DiscoveredCompany.confidence.desc(),
                DiscoveredCompany.created_at.desc(),
            )
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
