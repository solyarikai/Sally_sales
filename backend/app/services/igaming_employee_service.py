"""
iGaming Employee Search service.

Finds employees at selected companies via Apollo API.
Stores results in IGamingEmployee table.
"""
import asyncio
import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.igaming import IGamingCompany, IGamingEmployee, EmployeeSource

logger = logging.getLogger(__name__)

# Progress tracking
_search_progress: dict[str, dict] = {}  # task_id -> {processed, total, found, status, errors}


def get_search_progress(task_id: str) -> dict:
    return _search_progress.get(task_id, {"processed": 0, "total": 0, "found": 0, "status": "idle", "errors": []})


async def search_employees_apollo(
    session: AsyncSession,
    company_ids: list[int],
    titles: list[str],
    limit_per_company: int = 5,
    task_id: str = "default",
) -> dict:
    """
    Search for employees at given companies via Apollo.

    Args:
        company_ids: List of IGamingCompany IDs to search
        titles: Job titles to search for, e.g. ["CEO", "CTO", "Head of Payments"]
        limit_per_company: Max employees per company (1-10, Apollo limit)
        task_id: Unique ID for progress tracking

    Returns: {total_companies, processed, employees_found, errors}
    """
    from app.services.apollo_service import apollo_service

    if not apollo_service.is_configured():
        raise RuntimeError("Apollo API key not configured")

    # Load companies with websites
    companies = (await session.execute(
        select(IGamingCompany).where(
            IGamingCompany.id.in_(company_ids),
            IGamingCompany.website.isnot(None),
        )
    )).scalars().all()

    total = len(companies)
    _search_progress[task_id] = {"processed": 0, "total": total, "found": 0, "status": "running", "errors": []}

    processed = 0
    total_found = 0
    errors = []

    for company in companies:
        try:
            domain = company.website
            if not domain:
                processed += 1
                continue

            # Search Apollo
            people = await apollo_service.enrich_by_domain(
                domain=domain,
                limit=min(limit_per_company, 10),
                titles=titles if titles else None,
            )

            # Store results
            for person in people:
                # Check for duplicates
                existing = (await session.execute(
                    select(IGamingEmployee).where(
                        IGamingEmployee.company_id == company.id,
                        IGamingEmployee.email == person.get("email"),
                    ).limit(1)
                )).scalar_one_or_none() if person.get("email") else None

                if existing:
                    continue

                employee = IGamingEmployee(
                    company_id=company.id,
                    full_name=f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                    first_name=person.get("first_name"),
                    last_name=person.get("last_name"),
                    job_title=person.get("job_title"),
                    email=person.get("email"),
                    linkedin_url=person.get("linkedin_url"),
                    phone=person.get("phone"),
                    source=EmployeeSource.APOLLO,
                    search_query=", ".join(titles) if titles else None,
                    raw_data=person.get("raw_data"),
                )
                session.add(employee)
                total_found += 1

            # Update company employee count
            company.employees_count = (await session.execute(
                select(func.count(IGamingEmployee.id)).where(
                    IGamingEmployee.company_id == company.id
                )
            )).scalar() or 0

            processed += 1
            _search_progress[task_id].update({
                "processed": processed,
                "found": total_found,
            })

            if processed % 5 == 0:
                await session.flush()
                logger.info(f"Employee search: {processed}/{total} companies, {total_found} found")

        except Exception as e:
            processed += 1
            errors.append({"company": company.name, "error": str(e)})
            _search_progress[task_id]["errors"] = errors[-10:]
            logger.warning(f"Employee search error for {company.name}: {e}")

    await session.flush()

    _search_progress[task_id] = {
        "processed": processed,
        "total": total,
        "found": total_found,
        "status": "completed",
        "errors": errors[-10:],
    }

    logger.info(
        f"Employee search done: {processed}/{total} companies, "
        f"{total_found} employees found, {len(errors)} errors, "
        f"Apollo credits used: {apollo_service.credits_used}"
    )
    return {
        "total_companies": total,
        "processed": processed,
        "employees_found": total_found,
        "errors": len(errors),
        "apollo_credits_used": apollo_service.credits_used,
    }


async def search_employees_clay(
    session: AsyncSession,
    company_ids: list[int],
    titles: list[str],
    webhook_url: str,
    task_id: str = "default",
) -> dict:
    """
    Push company domains to Clay table for employee enrichment.

    Clay will process asynchronously — results come back via webhook.
    """
    from app.services.clay_service import clay_service

    companies = (await session.execute(
        select(IGamingCompany).where(
            IGamingCompany.id.in_(company_ids),
            IGamingCompany.website.isnot(None),
        )
    )).scalars().all()

    domains = [c.website for c in companies if c.website]
    extra_data = {"target_titles": ", ".join(titles)} if titles else {}

    result = await clay_service.push_domains_to_table(
        webhook_url=webhook_url,
        domains=domains,
        extra_data=extra_data,
    )

    logger.info(f"Clay employee search: pushed {result.get('pushed', 0)} domains")
    return {
        "pushed": result.get("pushed", 0),
        "total": len(domains),
        "errors": result.get("errors", 0),
    }
