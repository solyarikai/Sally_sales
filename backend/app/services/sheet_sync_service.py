"""Google Sheet Bidirectional Sync Service.

Handles three sync directions:
1. System → Replies tab (append new replies)
2. System → Leads tab (push/update warm leads, respecting column ownership)
3. Leads tab → System (poll qualification + client feedback → auto-transition status)

Column ownership rules:
- System writes A-O (lead data + status)
- Operator owns P-Q (internal notes, assignment)
- Client owns R-S (feedback, qualification)
- Status (J) is shared: forward-only writes, bidirectional reads
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.contact import Contact, Project
from app.models.reply import ProcessedReply
from app.services.google_sheets_service import google_sheets_service

logger = logging.getLogger(__name__)

# ── Status Mapping Constants (13-status funnel) ──

# CRM status → Sheet status label
CRM_TO_SHEET_STATUS = {
    # Legacy statuses (backward compat)
    "warm": "Заинтересован",
    "scheduling": "Запланирована",
    # 13-status funnel
    "interested": "Заинтересован",
    "negotiating_meeting": "Запланирована",
    "scheduled": "Назначена встреча",
    "meeting_held": "Была встреча",
    "meeting_no_show": "Не пришёл",
    "meeting_rescheduled": "Перенесена",
    "qualified": "Засчитываем",
    "not_qualified": "Не засчитываем",
    "not_interested": "Not interested",
    "ooo": "Out of office",
    "unsubscribed": "Unsubscribed",
}

# Sheet status → funnel rank (forward-only transitions)
SHEET_STATUS_RANK = {
    "Заинтересован": 1,
    "Пингануть": 1,
    "Not interested": 1,
    "Out of office": 1,
    "Unsubscribed": 1,
    "Запланирована": 2,
    "Назначена встреча": 3,
    "Была встреча": 4,
    "Не пришёл": 4,
    "Перенесена": 4,
    "Засчитываем": 5,
    "Не засчитываем": 5,
}

# Sheet qualification → CRM status auto-transition
QUALIFICATION_TO_STATUS = {
    "Засчитываем": "qualified",
    "Не засчитываем": "not_qualified",
}

# Sheet status → CRM status (for bidirectional detection)
SHEET_TO_CRM_STATUS = {
    "Заинтересован": "interested",
    "Пингануть": "interested",
    "Запланирована": "negotiating_meeting",
    "Назначена встреча": "scheduled",
    "Была встреча": "meeting_held",
    "Не пришёл": "meeting_no_show",
    "Перенесена": "meeting_rescheduled",
    "Засчитываем": "qualified",
    "Не засчитываем": "not_qualified",
    "Not interested": "not_interested",
    "Out of office": "ooo",
    "Unsubscribed": "unsubscribed",
}

# CRM status funnel rank (for comparing with sheet)
CRM_STATUS_RANK = {
    # Legacy
    "lead": 0,
    "contacted": 0,
    "warm": 1,
    "scheduling": 2,
    # 13-status funnel
    "to_be_sent": 0,
    "sent": 0,
    "interested": 1,
    "not_interested": 1,
    "ooo": 1,
    "unsubscribed": 1,
    "negotiating_meeting": 2,
    "scheduled": 3,
    "meeting_held": 4,
    "meeting_no_show": 4,
    "meeting_rescheduled": 4,
    "qualified": 5,
    "not_qualified": 5,
}

# Expected Leads tab headers (19 columns A-S)
EXPECTED_LEADS_HEADERS = [
    "Name", "Position", "Linkedin/Contact", "Company", "Telegram",
    "Website", "Company Location", "Employees", "Email #1",
    "Status", "Канал", "Дата ответа", "Hypothesis",
    "Prospect Comment", "Company Information",
    "Comment SALLY", "Кто взял в работу?", "Comment Easystaff", "Qualification",
]


def _col_letter(index: int) -> str:
    """Convert 0-based column index to letter (0=A, 1=B, ..., 25=Z)."""
    return chr(65 + index)


class SheetSyncService:
    """Bidirectional Google Sheet sync for project leads."""

    async def sync_replies_to_sheet(self, project_id: int) -> dict:
        """Push new replies to the Replies tab (append-only).

        Returns:
            Stats dict with rows_appended, total_synced, errors
        """
        stats = {"rows_appended": 0, "errors": []}

        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            if not project or not project.sheet_sync_config:
                stats["errors"].append("Project not found or no sheet config")
                return stats

            config = project.sheet_sync_config
            sheet_id = config.get("sheet_id")
            replies_tab = config.get("replies_tab", "Replies")
            last_sync = config.get("last_replies_sync_at")

            if not sheet_id:
                stats["errors"].append("No sheet_id configured")
                return stats

            # Query replies from this project's campaigns
            campaign_filters = project.campaign_filters or []
            if not campaign_filters:
                stats["errors"].append("No campaign_filters on project")
                return stats

            query = select(ProcessedReply).where(
                ProcessedReply.campaign_name.in_(campaign_filters)
            )
            if last_sync:
                try:
                    cutoff = datetime.fromisoformat(last_sync)
                    query = query.where(ProcessedReply.received_at > cutoff)
                except (ValueError, TypeError):
                    pass

            query = query.order_by(ProcessedReply.received_at.asc())
            result = await session.execute(query)
            replies = result.scalars().all()

            if not replies:
                return stats

            # Build email→Contact lookup for enrichment
            emails = list({r.lead_email.lower() for r in replies if r.lead_email})
            contact_map = {}
            if emails:
                contact_result = await session.execute(
                    select(Contact).where(
                        and_(
                            func.lower(Contact.email).in_(emails),
                            Contact.project_id == project_id,
                            Contact.deleted_at.is_(None),
                        )
                    )
                )
                for c in contact_result.scalars().all():
                    contact_map[c.email.lower()] = c

            # Build 16-column rows for Replies tab
            rows = []
            latest_received = None
            for reply in replies:
                contact = contact_map.get((reply.lead_email or "").lower())
                received_str = ""
                if reply.received_at:
                    received_str = reply.received_at.strftime("%d.%m.%Y")
                    if not latest_received or reply.received_at > latest_received:
                        latest_received = reply.received_at

                text = (reply.reply_text or reply.email_body or "")[:2000]

                # Extract from_email from raw webhook data if available
                from_email = ""
                raw = getattr(reply, 'raw_webhook_data', None)
                if isinstance(raw, dict):
                    from_email = raw.get("from_email", "")

                row = [
                    reply.lead_first_name or "",                         # first name
                    reply.lead_last_name or "",                          # last name
                    (contact.job_title if contact else "") or "",        # Position
                    (contact.linkedin_url if contact else "") or "",     # Linkedin
                    reply.lead_email or "",                              # target_lead_email
                    reply.lead_company or "",                            # Company
                    (contact.domain if contact else "") or "",           # Website
                    (contact.location if contact else "") or "",         # Company Location
                    "",                                                  # Employees
                    text,                                                # text
                    received_str,                                        # date
                    reply.campaign_name or "",                           # campaign
                    reply.campaign_id or "",                             # campaign_id
                    reply.category or "",                                # category
                    from_email,                                          # from_email
                    reply.lead_email or "",                              # to_email
                ]
                rows.append(row)

            # Batch append
            first_row = google_sheets_service.append_rows(sheet_id, replies_tab, rows)
            if first_row > 0:
                stats["rows_appended"] = len(rows)

                # Update config
                new_config = dict(config)
                new_config["last_replies_sync_at"] = (latest_received or datetime.utcnow()).isoformat()
                new_config["replies_synced_count"] = (config.get("replies_synced_count") or 0) + len(rows)
                project.sheet_sync_config = new_config
                await session.commit()
            else:
                stats["errors"].append("append_rows returned 0")

        return stats

    async def push_leads_to_sheet(self, project_id: int) -> dict:
        """Push/update warm leads to the Leads tab (system-owned columns A-O only).

        Respects forward-only status rule and never writes to operator/client columns P-S.

        Returns:
            Stats dict with new_rows, updated_rows, errors
        """
        stats = {"new_rows": 0, "updated_rows": 0, "errors": []}

        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            if not project or not project.sheet_sync_config:
                stats["errors"].append("Project not found or no sheet config")
                return stats

            config = project.sheet_sync_config
            sheet_id = config.get("sheet_id")
            leads_tab = config.get("leads_tab", "Leads")

            if not sheet_id:
                stats["errors"].append("No sheet_id configured")
                return stats

            # Validate headers
            headers = google_sheets_service.read_sheet_headers(sheet_id, leads_tab)
            if not headers:
                stats["errors"].append(f"Could not read headers from {leads_tab} tab")
                return stats

            # Relaxed header check — just verify key columns exist
            header_lower = [h.strip().lower() for h in headers]
            required = ["email #1", "status"]
            missing = [r for r in required if r not in header_lower]
            if missing:
                stats["errors"].append(f"Missing required columns: {missing}. Got: {headers[:10]}")
                return stats

            # Read existing sheet data to build email→row index
            sheet_rows = google_sheets_service.read_sheet_raw(sheet_id, leads_tab)
            email_col_idx = header_lower.index("email #1")
            status_col_idx = header_lower.index("status")

            email_to_row = {}
            sheet_statuses = {}
            for row_num, row in enumerate(sheet_rows[1:], start=2):  # skip header
                if len(row) > email_col_idx and row[email_col_idx]:
                    email_key = row[email_col_idx].strip().lower()
                    email_to_row[email_key] = row_num
                    if len(row) > status_col_idx:
                        sheet_statuses[email_key] = row[status_col_idx].strip()

            # Query contacts to push: warm+ leads (13-status + legacy)
            warm_statuses = [
                "warm", "scheduling",  # legacy
                "interested", "negotiating_meeting", "scheduled",
                "meeting_held", "meeting_no_show", "meeting_rescheduled",
                "qualified", "not_qualified",
            ]
            from sqlalchemy import or_
            contacts_result = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.deleted_at.is_(None),
                        or_(
                            and_(
                                Contact.has_replied == True,
                                Contact.reply_sentiment.in_(["warm", "positive"]),
                            ),
                            Contact.status.in_(warm_statuses),
                        ),
                    )
                )
            )
            contacts = contacts_result.scalars().all()

            if not contacts:
                return stats

            new_rows = []
            updates = []
            contacts_with_new_rows = []

            for contact in contacts:
                email_key = (contact.email or "").strip().lower()
                if not email_key:
                    continue

                # Build system-owned columns A-O (15 columns)
                name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                crm_status = contact.status or "warm"
                sheet_status_label = CRM_TO_SHEET_STATUS.get(crm_status, "")

                # Reply info
                reply_date = ""
                if contact.last_reply_at:
                    reply_date = contact.last_reply_at.strftime("%d.%m.%Y")

                # Hypothesis / campaign name
                hypothesis = ""
                if contact.campaigns:
                    first_campaign = contact.campaigns[0] if isinstance(contact.campaigns, list) else None
                    if isinstance(first_campaign, dict):
                        hypothesis = first_campaign.get("name", "")
                    elif isinstance(first_campaign, str):
                        hypothesis = first_campaign

                # Prospect comment (first reply snippet)
                prospect_comment = ""
                # Company info from gathering_details
                company_info = ""
                if contact.gathering_details and isinstance(contact.gathering_details, dict):
                    company_info = contact.gathering_details.get("description", "")[:500]

                system_cols = [
                    name,                                     # A: Name
                    contact.job_title or "",                   # B: Position
                    contact.linkedin_url or "",                # C: Linkedin/Contact
                    contact.company_name or "",                # D: Company
                    "",                                        # E: Telegram
                    contact.domain or "",                      # F: Website
                    contact.location or "",                    # G: Company Location
                    "",                                        # H: Employees
                    contact.email or "",                       # I: Email #1
                    sheet_status_label,                        # J: Status
                    contact.reply_channel or "",               # K: Канал
                    reply_date,                                # L: Дата ответа
                    hypothesis,                                # M: Hypothesis
                    prospect_comment,                          # N: Prospect Comment
                    company_info,                              # O: Company Information
                ]

                existing_row = email_to_row.get(email_key)

                if existing_row and contact.sheet_row:
                    # Update existing row — system columns A-O only
                    # Status column: forward-only rule
                    current_sheet_status = sheet_statuses.get(email_key, "")
                    current_rank = SHEET_STATUS_RANK.get(current_sheet_status, 0)
                    new_rank = SHEET_STATUS_RANK.get(sheet_status_label, 0)

                    if new_rank < current_rank:
                        # Don't downgrade — keep sheet status
                        system_cols[9] = current_sheet_status

                    # Build updates for columns A-O (first 15 columns)
                    for col_idx, value in enumerate(system_cols):
                        updates.append({
                            "range": f"{_col_letter(col_idx)}{existing_row}",
                            "values": [[value]],
                        })
                    stats["updated_rows"] += 1

                elif not existing_row:
                    # New lead — append full row (A-O, leave P-S empty)
                    full_row = system_cols + ["", "", "", ""]  # P, Q, R, S empty
                    new_rows.append(full_row)
                    contacts_with_new_rows.append(contact)

            # Batch update existing rows
            if updates:
                # Process in chunks of 500 to avoid API limits
                chunk_size = 500
                for i in range(0, len(updates), chunk_size):
                    chunk = updates[i:i + chunk_size]
                    google_sheets_service.update_cells(sheet_id, leads_tab, chunk)

            # Batch append new rows
            if new_rows:
                first_new = google_sheets_service.append_rows(sheet_id, leads_tab, new_rows)
                if first_new > 0:
                    stats["new_rows"] = len(new_rows)
                    # Store sheet_row on each contact
                    for offset, contact in enumerate(contacts_with_new_rows):
                        contact.sheet_row = first_new + offset
                else:
                    stats["errors"].append("Failed to append new rows")

            # Update config
            new_config = dict(config)
            new_config["last_leads_push_at"] = datetime.utcnow().isoformat()
            new_config["leads_pushed_count"] = (config.get("leads_pushed_count") or 0) + stats["new_rows"]
            project.sheet_sync_config = new_config
            await session.commit()

        return stats

    async def poll_qualification_from_sheet(self, project_id: int) -> dict:
        """Read client feedback from Leads tab → update CRM contacts.

        Reads columns J (Status), P (Comment SALLY), R (Comment Easystaff), S (Qualification).
        Auto-transitions contact status based on qualification values.

        Returns:
            Stats dict with contacts_updated, qualifications_changed, statuses_advanced, errors
        """
        stats = {
            "contacts_updated": 0,
            "qualifications_changed": 0,
            "statuses_advanced": 0,
            "errors": [],
        }

        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            if not project or not project.sheet_sync_config:
                stats["errors"].append("Project not found or no sheet config")
                return stats

            config = project.sheet_sync_config
            sheet_id = config.get("sheet_id")
            leads_tab = config.get("leads_tab", "Leads")

            if not sheet_id:
                stats["errors"].append("No sheet_id configured")
                return stats

            # Read full Leads tab
            sheet_rows = google_sheets_service.read_sheet_raw(sheet_id, leads_tab)
            if len(sheet_rows) < 2:
                return stats

            headers = sheet_rows[0]
            header_lower = [h.strip().lower() for h in headers]

            # Find column indices
            def find_col(name: str) -> int:
                try:
                    return header_lower.index(name.lower())
                except ValueError:
                    return -1

            email_idx = find_col("Email #1")
            status_idx = find_col("Status")
            comment_sally_idx = find_col("Comment SALLY")
            comment_client_idx = find_col("Comment Easystaff")
            qualification_idx = find_col("Qualification")

            if email_idx < 0:
                stats["errors"].append("Email #1 column not found")
                return stats

            # Build email → contact lookup
            contacts_result = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.deleted_at.is_(None),
                    )
                )
            )
            contact_map = {}
            for c in contacts_result.scalars().all():
                if c.email:
                    contact_map[c.email.strip().lower()] = c

            # Process each row
            for row_num, row in enumerate(sheet_rows[1:], start=2):
                def get_cell(idx: int) -> str:
                    if idx < 0 or idx >= len(row):
                        return ""
                    return (row[idx] or "").strip()

                email = get_cell(email_idx).lower()
                if not email:
                    continue

                contact = contact_map.get(email)
                if not contact:
                    continue

                changed = False

                # Update sheet_row if not set
                if not contact.sheet_row:
                    contact.sheet_row = row_num
                    changed = True

                # Qualification (col S) — auto-transition status
                if qualification_idx >= 0:
                    sheet_qual = get_cell(qualification_idx)
                    if sheet_qual and sheet_qual != (contact.sheet_qualification or ""):
                        contact.sheet_qualification = sheet_qual
                        changed = True
                        stats["qualifications_changed"] += 1

                        # Auto-transition
                        new_status = QUALIFICATION_TO_STATUS.get(sheet_qual)
                        if new_status and contact.status != new_status:
                            old_status = contact.status
                            contact.status = new_status
                            logger.info(
                                f"Auto-transition: {contact.email} "
                                f"{old_status} → {new_status} (qualification: {sheet_qual})"
                            )

                            # Sync to SmartLead if qualified
                            if new_status == "qualified":
                                await self._sync_status_to_smartlead(contact, session)

                # Comment Easystaff (col R) → sheet_client_comment
                if comment_client_idx >= 0:
                    client_comment = get_cell(comment_client_idx)
                    if client_comment and client_comment != (contact.sheet_client_comment or ""):
                        contact.sheet_client_comment = client_comment
                        changed = True

                # Comment SALLY (col P) → contact.notes (informational)
                if comment_sally_idx >= 0:
                    sally_comment = get_cell(comment_sally_idx)
                    if sally_comment and sally_comment != (contact.notes or ""):
                        contact.notes = sally_comment
                        changed = True

                # Status (col J) — bidirectional: if sheet outranks CRM, advance CRM
                if status_idx >= 0:
                    sheet_status = get_cell(status_idx)
                    if sheet_status:
                        sheet_rank = SHEET_STATUS_RANK.get(sheet_status, 0)
                        crm_rank = CRM_STATUS_RANK.get(contact.status or "", 0)

                        if sheet_rank > crm_rank:
                            new_crm = SHEET_TO_CRM_STATUS.get(sheet_status)
                            if new_crm and contact.status != new_crm:
                                old = contact.status
                                contact.status = new_crm
                                changed = True
                                stats["statuses_advanced"] += 1
                                logger.info(
                                    f"Sheet→CRM status advance: {contact.email} "
                                    f"{old} → {new_crm} (sheet: {sheet_status})"
                                )

                if changed:
                    stats["contacts_updated"] += 1

            # Update config
            new_config = dict(config)
            new_config["last_qualification_poll_at"] = datetime.utcnow().isoformat()
            project.sheet_sync_config = new_config
            await session.commit()

        return stats

    async def _sync_status_to_smartlead(self, contact: Contact, session: AsyncSession):
        """Sync contact status to SmartLead when auto-transitioning to qualified."""
        import os
        import httpx
        try:
            if not contact.smartlead_id:
                return

            api_key = os.getenv("SMARTLEAD_API_KEY")
            if not api_key:
                return

            # Get campaign ID
            campaign_id = None
            if contact.campaigns:
                campaigns = contact.campaigns if isinstance(contact.campaigns, list) else []
                for c in campaigns:
                    if isinstance(c, dict) and c.get("source") == "smartlead":
                        campaign_id = c.get("id")
                        break

            if not campaign_id:
                return

            # qualified = category 77597, pause lead on qualification
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{contact.smartlead_id}/category?api_key={api_key}",
                    json={"category_id": 77597, "pause_lead": True},
                    timeout=30,
                )
                if resp.status_code == 200:
                    logger.info(f"Synced qualified status to SmartLead for {contact.email}")
                else:
                    logger.warning(f"SmartLead sync returned {resp.status_code} for {contact.email}")
        except Exception as e:
            logger.warning(f"Failed to sync status to SmartLead for {contact.email}: {e}")


# Singleton
sheet_sync_service = SheetSyncService()
