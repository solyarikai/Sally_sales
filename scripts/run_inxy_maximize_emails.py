"""
Inxy — Maximize email coverage for all 305 target companies.

Problems to fix:
1. Apollo found 0 contacts for 229 targets — re-enrich WITHOUT title filter
2. 36 Apollo contacts have LinkedIn but no email — FindyMail LinkedIn lookup
3. 10 Apollo emails failed verification — FindyMail find by name+domain
4. All new Apollo emails → verify via FindyMail
5. Re-export clean sheet
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("inxy_max")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROJECT_ID = 48
COMPANY_ID = 1


async def step1_rerun_apollo_no_filter():
    """Re-enrich the 229 targets that got 0 Apollo contacts — NO title filter this time."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany, ExtractedContact, ContactSource
    from sqlalchemy import select, or_

    logger.info("=" * 60)
    logger.info("STEP 1: Re-run Apollo for 229 targets WITHOUT title filter")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
                or_(
                    DiscoveredCompany.apollo_people_count.is_(None),
                    DiscoveredCompany.apollo_people_count == 0,
                ),
            )
        )
        targets = result.scalars().all()
        logger.info(f"Targets with 0 Apollo contacts: {len(targets)}")

        apollo_service.reset_credits()
        found_total = 0
        with_email = 0

        for i, dc in enumerate(targets):
            try:
                # No title filter — get ANY people
                people = await apollo_service.enrich_by_domain(dc.domain, limit=5)

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
                        is_verified=False,  # will verify via FindyMail
                        raw_data=person.get("raw_data"),
                    )
                    session.add(ec)
                    if person.get("email"):
                        with_email += 1

                dc.apollo_people_count = len(people)
                dc.apollo_enriched_at = datetime.utcnow()
                dc.contacts_count = (dc.contacts_count or 0) + len(people)
                found_total += len(people)

                if (i + 1) % 50 == 0:
                    await session.commit()
                    logger.info(f"  Progress: {i+1}/{len(targets)} | people={found_total} emails={with_email} credits={apollo_service.credits_used}")

            except Exception as e:
                logger.error(f"  {dc.domain}: {e}")

        await session.commit()
        logger.info(f"Apollo re-enrichment done: {found_total} people, {with_email} emails, {apollo_service.credits_used} credits")


async def step2_findymail_all():
    """
    FindyMail for ALL Apollo contacts:
    1. Verify all unverified Apollo emails
    2. LinkedIn lookup for contacts with LinkedIn but no email
    3. Name+domain find for contacts with name but no email and no LinkedIn
    4. For failed verifications — try find by name+domain
    """
    from app.db import async_session_maker
    from app.services.findymail_service import findymail_service
    from app.models.pipeline import ExtractedContact, DiscoveredCompany, ContactSource
    from app.core.config import settings
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("STEP 2: FindyMail — verify + find for ALL Apollo contacts")
    logger.info("=" * 60)

    if hasattr(settings, "FINDYMAIL_API_KEY") and settings.FINDYMAIL_API_KEY:
        findymail_service.set_api_key(settings.FINDYMAIL_API_KEY)
    elif os.environ.get("FINDYMAIL_API_KEY"):
        findymail_service.set_api_key(os.environ["FINDYMAIL_API_KEY"])

    if not findymail_service.is_connected():
        logger.error("FindyMail not configured!")
        return

    credits = await findymail_service.get_credits()
    logger.info(f"FindyMail credits: {credits}")

    async with async_session_maker() as session:
        dc_ids_q = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        dc_ids = [r[0] for r in dc_ids_q.fetchall()]

        # --- Part A: Verify unverified Apollo emails ---
        unverified_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.email.isnot(None),
                ExtractedContact.source == ContactSource.APOLLO,
                ExtractedContact.verification_method.is_(None),
            )
        )
        unverified = unverified_q.scalars().all()
        logger.info(f"Part A: {len(unverified)} Apollo emails to verify")

        verified = 0
        invalid = 0
        for ec in unverified:
            try:
                result = await findymail_service.verify_email(ec.email)
                if result.get("success"):
                    ec.is_verified = result.get("verified", False)
                    ec.verification_method = "findymail"
                    if ec.is_verified:
                        verified += 1
                    else:
                        invalid += 1
            except Exception as e:
                logger.error(f"  Verify error {ec.email}: {e}")

            if (verified + invalid) % 20 == 0 and (verified + invalid) > 0:
                await session.commit()
                logger.info(f"  A progress: {verified} valid, {invalid} invalid")

        await session.commit()
        logger.info(f"Part A done: {verified} valid, {invalid} invalid")

        # --- Part B: FindyMail find for invalid emails ---
        failed_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.source == ContactSource.APOLLO,
                ExtractedContact.verification_method == "findymail",
                ExtractedContact.is_verified == False,
                ExtractedContact.first_name.isnot(None),
                ExtractedContact.last_name.isnot(None),
            )
        )
        failed = failed_q.scalars().all()
        logger.info(f"Part B: {len(failed)} failed emails to re-find")

        replaced = 0
        for ec in failed:
            try:
                dc_q = await session.execute(
                    select(DiscoveredCompany.domain).where(DiscoveredCompany.id == ec.discovered_company_id)
                )
                domain = dc_q.scalar()
                if not domain:
                    continue

                # Try LinkedIn first
                if ec.linkedin_url:
                    result = await findymail_service.find_email_by_linkedin(ec.linkedin_url)
                    if result.get("success") and result.get("email"):
                        ec.email = result["email"]
                        ec.is_verified = result.get("verified", False)
                        ec.verification_method = "findymail_linkedin"
                        replaced += 1
                        continue

                # Fallback: name + domain
                result = await findymail_service.find_email_by_name(
                    f"{ec.first_name} {ec.last_name}", domain
                )
                if result.get("success") and result.get("email"):
                    ec.email = result["email"]
                    ec.is_verified = result.get("verified", False)
                    ec.verification_method = "findymail_found"
                    replaced += 1
            except Exception as e:
                logger.error(f"  Find error: {e}")

        await session.commit()
        logger.info(f"Part B done: {replaced} replaced")

        # --- Part C: LinkedIn lookup for contacts WITHOUT email ---
        no_email_linkedin_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.source == ContactSource.APOLLO,
                ExtractedContact.email.is_(None),
                ExtractedContact.linkedin_url.isnot(None),
                ExtractedContact.verification_method.is_(None),
            )
        )
        no_email_linkedin = no_email_linkedin_q.scalars().all()
        logger.info(f"Part C: {len(no_email_linkedin)} contacts with LinkedIn, no email")

        found_linkedin = 0
        for ec in no_email_linkedin:
            try:
                result = await findymail_service.find_email_by_linkedin(ec.linkedin_url)
                if result.get("success") and result.get("email"):
                    ec.email = result["email"]
                    ec.is_verified = result.get("verified", False)
                    ec.verification_method = "findymail_linkedin"
                    found_linkedin += 1
                else:
                    ec.verification_method = "findymail_linkedin_notfound"
            except Exception as e:
                logger.error(f"  LinkedIn find error: {e}")

            if found_linkedin % 10 == 0 and found_linkedin > 0:
                await session.commit()

        await session.commit()
        logger.info(f"Part C done: {found_linkedin} found via LinkedIn")

        # --- Part D: Name+domain for contacts without email AND without LinkedIn ---
        no_email_name_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.source == ContactSource.APOLLO,
                ExtractedContact.email.is_(None),
                ExtractedContact.linkedin_url.is_(None),
                ExtractedContact.first_name.isnot(None),
                ExtractedContact.last_name.isnot(None),
                ExtractedContact.verification_method.is_(None),
            )
        )
        no_email_name = no_email_name_q.scalars().all()
        logger.info(f"Part D: {len(no_email_name)} contacts with name only, no email/LinkedIn")

        found_name = 0
        for ec in no_email_name:
            try:
                dc_q = await session.execute(
                    select(DiscoveredCompany.domain).where(DiscoveredCompany.id == ec.discovered_company_id)
                )
                domain = dc_q.scalar()
                if not domain:
                    continue

                result = await findymail_service.find_email_by_name(
                    f"{ec.first_name} {ec.last_name}", domain
                )
                if result.get("success") and result.get("email"):
                    ec.email = result["email"]
                    ec.is_verified = result.get("verified", False)
                    ec.verification_method = "findymail_found"
                    found_name += 1
                else:
                    ec.verification_method = "findymail_name_notfound"
            except Exception as e:
                logger.error(f"  Name find error: {e}")

        await session.commit()

        # Final stats
        logger.info("=" * 60)
        logger.info("FINDYMAIL COMPLETE")
        logger.info(f"  Verified: {verified}")
        logger.info(f"  Invalid: {invalid}")
        logger.info(f"  Replaced (failed→found): {replaced}")
        logger.info(f"  Found via LinkedIn: {found_linkedin}")
        logger.info(f"  Found via name+domain: {found_name}")
        logger.info("=" * 60)


async def main():
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("INXY MAXIMIZE EMAIL COVERAGE")
    logger.info("=" * 60)

    await step1_rerun_apollo_no_filter()
    await step2_findymail_all()

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"Done in {elapsed:.0f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    asyncio.run(main())
