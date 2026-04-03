"""
Domain Lookup Service — unified 6-table aggregation for any domain.

Given a domain name, queries all relevant tables (domains, search_results,
discovered_companies, extracted_contacts, contacts, contact_activities,
pipeline_events) and returns a complete profile.

Used by the chat `lookup_domain` action.
"""
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.domain_service import normalize_domain

logger = logging.getLogger(__name__)

MAX_DOMAINS_PER_REQUEST = 5


class DomainLookupService:

    async def lookup(
        self,
        session: AsyncSession,
        raw_domains: List[str],
        company_id: int,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Look up everything known about one or more domains.
        Returns {domain: profile_dict} for each domain.
        """
        domains = []
        for raw in raw_domains[:MAX_DOMAINS_PER_REQUEST]:
            d = normalize_domain(raw)
            if d:
                domains.append(d)
        if not domains:
            return {}

        profiles = {}
        for domain in domains:
            profiles[domain] = await self._lookup_single(session, domain, company_id, project_id)
        return profiles

    async def _lookup_single(
        self,
        session: AsyncSession,
        domain: str,
        company_id: int,
        project_id: Optional[int],
    ) -> Dict[str, Any]:
        profile: Dict[str, Any] = {"domain": domain}

        # 1. Global domain registry
        row = (await session.execute(sql_text(
            "SELECT id, status, source, first_seen, last_seen, times_seen "
            "FROM domains WHERE domain = :d"
        ), {"d": domain})).fetchone()
        if row:
            profile["registry"] = {
                "status": row.status,
                "source": row.source,
                "first_seen": str(row.first_seen) if row.first_seen else None,
                "last_seen": str(row.last_seen) if row.last_seen else None,
                "times_seen": row.times_seen,
            }

        # 2. Search results (company-scoped, optionally project-filtered)
        sr_sql = """
            SELECT sr.id, sr.domain, sr.is_target, sr.confidence, sr.reasoning,
                   sr.company_info, sr.scores, sr.review_status, sr.review_note,
                   sr.matched_segment, sr.analyzed_at, sr.project_id,
                   sj.search_engine, sj.id as job_id
            FROM search_results sr
            JOIN search_jobs sj ON sr.search_job_id = sj.id
            WHERE sr.domain = :d AND sj.company_id = :cid
        """
        params: Dict[str, Any] = {"d": domain, "cid": company_id}
        if project_id:
            sr_sql += " AND sr.project_id = :pid"
            params["pid"] = project_id
        sr_sql += " ORDER BY sr.analyzed_at DESC NULLS LAST LIMIT 5"
        sr_rows = (await session.execute(sql_text(sr_sql), params)).fetchall()
        if sr_rows:
            best = sr_rows[0]
            profile["search"] = {
                "is_target": best.is_target,
                "confidence": best.confidence,
                "reasoning": best.reasoning,
                "company_info": best.company_info,
                "scores": best.scores,
                "review_status": best.review_status,
                "review_note": best.review_note,
                "matched_segment": best.matched_segment,
                "total_results": len(sr_rows),
                "engines": list({r.search_engine for r in sr_rows}),
            }

        # 3. Discovered company (pipeline record)
        dc_sql = """
            SELECT id, name, status, is_target, confidence, reasoning,
                   contacts_count, apollo_people_count, apollo_enriched_at,
                   project_id, created_at
            FROM discovered_companies
            WHERE domain = :d AND company_id = :cid
        """
        dc_params: Dict[str, Any] = {"d": domain, "cid": company_id}
        if project_id:
            dc_sql += " AND project_id = :pid"
            dc_params["pid"] = project_id
        dc_sql += " ORDER BY created_at DESC LIMIT 1"
        dc_row = (await session.execute(sql_text(dc_sql), dc_params)).fetchone()
        dc_id = None
        if dc_row:
            dc_id = dc_row.id
            profile["pipeline"] = {
                "id": dc_row.id,
                "name": dc_row.name,
                "status": dc_row.status,
                "is_target": dc_row.is_target,
                "confidence": dc_row.confidence,
                "contacts_count": dc_row.contacts_count,
                "apollo_people_count": dc_row.apollo_people_count,
                "apollo_enriched_at": str(dc_row.apollo_enriched_at) if dc_row.apollo_enriched_at else None,
                "project_id": dc_row.project_id,
            }

        # 4. Extracted contacts (from discovered company)
        if dc_id:
            ec_rows = (await session.execute(sql_text("""
                SELECT email, first_name, last_name, job_title, source,
                       linkedin_url, is_verified, contact_id
                FROM extracted_contacts
                WHERE discovered_company_id = :dc_id
                ORDER BY created_at DESC LIMIT 20
            """), {"dc_id": dc_id})).fetchall()
            if ec_rows:
                profile["extracted_contacts"] = [
                    {
                        "email": r.email,
                        "name": " ".join(filter(None, [r.first_name, r.last_name])),
                        "job_title": r.job_title,
                        "source": r.source,
                        "linkedin": r.linkedin_url,
                        "verified": r.is_verified,
                        "promoted_to_crm": r.contact_id is not None,
                    }
                    for r in ec_rows
                ]

        # 5. CRM contacts (by domain match)
        crm_rows = (await session.execute(sql_text("""
            SELECT id, email, first_name, last_name, company_name,
                   job_title, status, last_reply_at, platform_state, source
            FROM contacts
            WHERE company_id = :cid AND domain = :d AND deleted_at IS NULL
            ORDER BY last_reply_at DESC NULLS LAST, created_at DESC
            LIMIT 20
        """), {"cid": company_id, "d": domain})).fetchall()
        if crm_rows:
            profile["crm_contacts"] = [
                {
                    "id": r.id,
                    "email": r.email,
                    "name": " ".join(filter(None, [r.first_name, r.last_name])),
                    "job_title": r.job_title,
                    "status": r.status,
                    "has_replied": r.last_reply_at is not None,
                    "source": r.source,
                }
                for r in crm_rows
            ]

            # 6. Contact activities (from CRM contacts)
            contact_ids = [r.id for r in crm_rows]
            if contact_ids:
                # Build IN clause safely with positional params
                placeholders = ", ".join(f":cid_{i}" for i in range(len(contact_ids)))
                act_params: Dict[str, Any] = {f"cid_{i}": cid for i, cid in enumerate(contact_ids)}
                act_rows = (await session.execute(sql_text(f"""
                    SELECT ca.contact_id, ca.activity_type, ca.channel, ca.direction,
                           ca.subject, ca.snippet, ca.activity_at
                    FROM contact_activities ca
                    WHERE ca.contact_id IN ({placeholders})
                    ORDER BY ca.activity_at DESC
                    LIMIT 30
                """), act_params)).fetchall()
                if act_rows:
                    profile["activities"] = [
                        {
                            "contact_id": r.contact_id,
                            "type": r.activity_type,
                            "channel": r.channel,
                            "direction": r.direction,
                            "subject": r.subject,
                            "snippet": (r.snippet or "")[:120],
                            "at": str(r.activity_at) if r.activity_at else None,
                        }
                        for r in act_rows
                    ]

        # 7. Pipeline events (from discovered company)
        if dc_id:
            pe_rows = (await session.execute(sql_text("""
                SELECT event_type, detail, created_at
                FROM pipeline_events
                WHERE discovered_company_id = :dc_id
                ORDER BY created_at DESC LIMIT 15
            """), {"dc_id": dc_id})).fetchall()
            if pe_rows:
                profile["pipeline_events"] = [
                    {
                        "type": r.event_type,
                        "detail": r.detail,
                        "at": str(r.created_at) if r.created_at else None,
                    }
                    for r in pe_rows
                ]

        return profile

    def format_as_markdown(self, profiles: Dict[str, Dict[str, Any]]) -> str:
        """Format lookup profiles into readable markdown for chat reply."""
        if not profiles:
            return "No domains to look up."

        parts = []
        for domain, p in profiles.items():
            lines = [f"## {domain}"]

            # Company name + pipeline status
            name = None
            if p.get("pipeline"):
                name = p["pipeline"].get("name")
                lines.append(f"**Company:** {name or 'Unknown'}")
                lines.append(f"**Pipeline status:** {p['pipeline']['status']}")
            elif p.get("search") and p["search"].get("company_info"):
                ci = p["search"]["company_info"]
                name = ci.get("name") if isinstance(ci, dict) else None
                if name:
                    lines.append(f"**Company:** {name}")

            # Domain registry
            if p.get("registry"):
                reg = p["registry"]
                seen_info = f"seen {reg['times_seen']}x" if reg.get("times_seen") else ""
                first = reg.get("first_seen", "")[:10] if reg.get("first_seen") else ""
                lines.append(f"**Domain status:** {reg['status'].upper()} ({seen_info}, first: {first})")

            # Search verdict
            if p.get("search"):
                s = p["search"]
                verdict = "TARGET" if s["is_target"] else "NOT TARGET"
                conf = f"{round(s['confidence'] * 100)}%" if s.get("confidence") else "N/A"
                lines.append(f"\n**Search verdict:** {verdict} ({conf} confidence)")
                if s.get("reasoning"):
                    reason = s["reasoning"][:200]
                    lines.append(f"**Reasoning:** {reason}")
                if s.get("matched_segment"):
                    lines.append(f"**Segment:** {s['matched_segment']}")
                if s.get("review_status"):
                    lines.append(f"**Review:** {s['review_status']}")
                if s.get("engines"):
                    lines.append(f"**Found via:** {', '.join(s['engines'])}")

            # Extracted contacts
            if p.get("extracted_contacts"):
                ecs = p["extracted_contacts"]
                lines.append(f"\n**Extracted contacts:** {len(ecs)}")
                for ec in ecs[:8]:
                    name_str = ec["name"] or ec.get("email", "?")
                    title = f" — {ec['job_title']}" if ec.get("job_title") else ""
                    src = f" [{ec['source']}]" if ec.get("source") else ""
                    promoted = " (in CRM)" if ec.get("promoted_to_crm") else ""
                    lines.append(f"- {name_str} ({ec.get('email', 'no email')}){title}{src}{promoted}")

            # CRM contacts
            if p.get("crm_contacts"):
                crms = p["crm_contacts"]
                replied_count = sum(1 for c in crms if c.get("has_replied"))
                lines.append(f"\n**CRM contacts:** {len(crms)} ({replied_count} replied)")
                for c in crms[:8]:
                    name_str = c["name"] or c.get("email", "?")
                    status_str = c["status"]
                    if c.get("has_replied"):
                        status_str = "REPLIED"
                    lines.append(f"- **{name_str}** ({status_str})")

            # Activities
            if p.get("activities"):
                acts = p["activities"]
                lines.append(f"\n**Recent activity:** {len(acts)} events")
                for a in acts[:10]:
                    date = a["at"][:10] if a.get("at") else "?"
                    direction = a.get("direction", "")
                    snippet = a.get("snippet", "")
                    if snippet:
                        snippet = f": {snippet[:80]}"
                    lines.append(f"- [{date}] {direction} {a['type']}{snippet}")

            # Pipeline events
            if p.get("pipeline_events"):
                pes = p["pipeline_events"]
                lines.append(f"\n**Pipeline events:** {len(pes)}")
                for pe in pes[:6]:
                    date = pe["at"][:10] if pe.get("at") else "?"
                    lines.append(f"- [{date}] {pe['type']}")

            # Nothing found
            if not any(p.get(k) for k in ["registry", "search", "pipeline", "crm_contacts", "extracted_contacts"]):
                lines.append("\nNo data found for this domain.")

            parts.append("\n".join(lines))

        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _extract_campaign_names(campaigns) -> List[str]:
        """Extract campaign names from the campaigns JSON field."""
        if not campaigns:
            return []
        if isinstance(campaigns, list):
            names = []
            for c in campaigns:
                if isinstance(c, dict):
                    names.append(c.get("name", c.get("campaign_name", "?")))
                elif isinstance(c, str):
                    names.append(c)
            return names[:3]
        return []


domain_lookup_service = DomainLookupService()
