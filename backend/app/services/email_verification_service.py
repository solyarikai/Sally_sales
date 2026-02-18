"""Email Verification Service — wraps Findymail with 90-day cache + batch operations.

Never calls Findymail directly in the pipeline. Only runs when operator enables it
via chat or triggers it manually.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import EmailVerification, ExtractedContact
from app.models.contact import Contact
from app.services.findymail_service import findymail_service

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 90
COST_PER_VERIFY = Decimal("0.001")


class EmailVerificationService:
    """Wraps findymail_service with caching, tracking, and batch operations."""

    async def verify_email(
        self,
        session: AsyncSession,
        email: str,
        project_id: Optional[int] = None,
        company_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        extracted_contact_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Verify a single email with 90-day cache.

        Returns: {email, result, is_valid, provider, cached, cost_usd}
        """
        # 1. Check cache
        cached = await self._get_cached(session, email)
        if cached:
            return {
                "email": email,
                "result": cached.result,
                "is_valid": cached.is_valid,
                "provider": cached.provider,
                "cached": True,
                "cost_usd": 0,
            }

        # 2. Call Findymail API
        if not findymail_service.is_connected():
            return {"email": email, "result": "error", "is_valid": None, "error": "Findymail not connected", "cached": False, "cost_usd": 0}

        api_result = await findymail_service.verify_email(email)

        if not api_result.get("success"):
            # Log error but don't cache it
            ev = EmailVerification(
                email=email,
                service="findymail",
                result="error",
                is_valid=None,
                raw_response=api_result,
                cost_usd=COST_PER_VERIFY,
                verified_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=1),  # short TTL for errors
                contact_id=contact_id,
                extracted_contact_id=extracted_contact_id,
                company_id=company_id,
                project_id=project_id,
            )
            session.add(ev)
            return {
                "email": email,
                "result": "error",
                "is_valid": None,
                "error": api_result.get("error"),
                "cached": False,
                "cost_usd": float(COST_PER_VERIFY),
            }

        # 3. Parse result
        is_valid = api_result.get("verified", False)
        provider = api_result.get("provider")
        data = api_result.get("data", {})

        # Determine result category
        if is_valid:
            result = "valid"
        else:
            # Check for catch_all or other statuses from API response
            result = "invalid"
            if data.get("catch_all"):
                result = "catch_all"

        # 4. Store in DB (90-day cache)
        now = datetime.utcnow()
        ev = EmailVerification(
            email=email,
            service="findymail",
            result=result,
            is_valid=is_valid,
            provider=provider,
            raw_response=api_result,
            cost_usd=COST_PER_VERIFY,
            verified_at=now,
            expires_at=now + timedelta(days=CACHE_TTL_DAYS),
            contact_id=contact_id,
            extracted_contact_id=extracted_contact_id,
            company_id=company_id,
            project_id=project_id,
        )
        session.add(ev)

        # 5. Update Contact if linked
        if contact_id:
            contact_result = await session.execute(
                select(Contact).where(Contact.id == contact_id)
            )
            contact = contact_result.scalar_one_or_none()
            if contact:
                contact.is_email_verified = True
                contact.email_verified_at = now
                contact.email_verification_result = result

        # 6. Update ExtractedContact if linked
        if extracted_contact_id:
            ec_result = await session.execute(
                select(ExtractedContact).where(ExtractedContact.id == extracted_contact_id)
            )
            ec = ec_result.scalar_one_or_none()
            if ec:
                ec.is_verified = is_valid
                ec.verification_method = "findymail"

        return {
            "email": email,
            "result": result,
            "is_valid": is_valid,
            "provider": provider,
            "cached": False,
            "cost_usd": float(COST_PER_VERIFY),
        }

    async def verify_batch(
        self,
        session: AsyncSession,
        emails: List[str],
        project_id: Optional[int] = None,
        company_id: Optional[int] = None,
        max_credits: int = 100,
        email_to_contact: Optional[Dict[str, int]] = None,
        email_to_extracted: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Verify a batch of emails with budget guardrail.

        Returns: {results: {email: result_dict}, stats: {total, verified, valid, invalid, cached, cost_usd}}
        """
        email_to_contact = email_to_contact or {}
        email_to_extracted = email_to_extracted or {}

        results = {}
        stats = {"total": len(emails), "verified": 0, "valid": 0, "invalid": 0, "cached": 0, "errors": 0, "cost_usd": 0.0}
        credits_used = 0

        for email in emails:
            if credits_used >= max_credits:
                logger.info(f"Budget cap reached ({max_credits} credits), stopping verification")
                break

            result = await self.verify_email(
                session, email,
                project_id=project_id,
                company_id=company_id,
                contact_id=email_to_contact.get(email),
                extracted_contact_id=email_to_extracted.get(email),
            )
            results[email] = result

            if result.get("cached"):
                stats["cached"] += 1
            else:
                credits_used += 1

            stats["verified"] += 1
            stats["cost_usd"] += result.get("cost_usd", 0)

            if result.get("result") == "valid":
                stats["valid"] += 1
            elif result.get("result") in ("invalid", "catch_all"):
                stats["invalid"] += 1
            elif result.get("result") == "error":
                stats["errors"] += 1

        await session.flush()
        return {"results": results, "stats": stats}

    async def get_stats(
        self,
        session: AsyncSession,
        project_id: Optional[int] = None,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get verification statistics for a project or company."""
        filters = []
        if project_id:
            filters.append(EmailVerification.project_id == project_id)
        if company_id:
            filters.append(EmailVerification.company_id == company_id)

        # Total verifications
        total_q = await session.execute(
            select(func.count()).select_from(EmailVerification).where(*filters) if filters
            else select(func.count()).select_from(EmailVerification)
        )
        total = total_q.scalar() or 0

        # By result
        result_q = await session.execute(
            select(EmailVerification.result, func.count())
            .where(*filters)
            .group_by(EmailVerification.result) if filters
            else select(EmailVerification.result, func.count())
            .group_by(EmailVerification.result)
        )
        result_counts = dict(result_q.fetchall())

        # Total cost
        cost_q = await session.execute(
            select(func.sum(EmailVerification.cost_usd))
            .where(*filters) if filters
            else select(func.sum(EmailVerification.cost_usd))
        )
        total_cost = cost_q.scalar() or Decimal("0")

        # Unique emails verified
        unique_q = await session.execute(
            select(func.count(func.distinct(EmailVerification.email)))
            .where(*filters) if filters
            else select(func.count(func.distinct(EmailVerification.email)))
        )
        unique_emails = unique_q.scalar() or 0

        return {
            "total_verifications": total,
            "unique_emails": unique_emails,
            "valid": result_counts.get("valid", 0),
            "invalid": result_counts.get("invalid", 0),
            "catch_all": result_counts.get("catch_all", 0),
            "errors": result_counts.get("error", 0),
            "total_cost_usd": float(total_cost),
        }

    async def _get_cached(self, session: AsyncSession, email: str) -> Optional[EmailVerification]:
        """Check for a non-expired cached verification result."""
        now = datetime.utcnow()
        result = await session.execute(
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.expires_at > now,
                EmailVerification.result != "error",
            )
            .order_by(EmailVerification.verified_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


# Module-level singleton
email_verification_service = EmailVerificationService()
