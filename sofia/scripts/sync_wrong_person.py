#!/usr/bin/env python3
"""
Sync Wrong Person replies to a SmartLead referral campaign.
Runs 2x daily via cron (09:00 and 17:00 UTC).

Usage:
  python3 sync_wrong_person.py --project OnSocial --chat-id 7380803777
  python3 sync_wrong_person.py --project EasyStaff --chat-id 7380803777
  python3 sync_wrong_person.py --project OnSocial --campaign-id 3092917 --chat-id 7380803777

Auto-discovery:
  --campaign-id is optional. The script finds the WRONG-PERSON campaign
  in SmartLead by matching the project name + 'WRONG' + 'PERSON'
  in the campaign name. New projects just need a campaign named like
  c-{Project}_WRONG-PERSON-referral.

Flow:
  1. Auto-discover WRONG-PERSON campaign (or use --campaign-id override)
  2. Query processed_replies for wrong_person + project filter
  3. Skip already-synced (tracked in contact_activities)
  4. Add to SmartLead campaign via SmartLead API directly
  5. Mark synced in contact_activities
  6. Send Telegram report
"""

import os
import argparse
import json
import logging
from datetime import datetime
import psycopg2
import psycopg2.extras
import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SmartLead config
SMARTLEAD_API_KEY = os.environ.get('SMARTLEAD_API_KEY', '')
SMARTLEAD_BASE_URL = 'https://server.smartlead.ai/api/v1'

# Telegram config
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# DB config
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))
DB_NAME = os.environ.get('DB_NAME', 'leadgen')
DB_USER = os.environ.get('DB_USER', 'leadgen')
DB_PASS = os.environ.get('DB_PASSWORD', 'leadgen_secret')


def fetch_smartlead_campaigns():
    """Fetch all campaigns from SmartLead. Cached per run."""
    if not SMARTLEAD_API_KEY:
        logger.error("SMARTLEAD_API_KEY not set")
        return []

    resp = httpx.get(
        f'{SMARTLEAD_BASE_URL}/campaigns',
        params={'api_key': SMARTLEAD_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    camps = resp.json()
    if isinstance(camps, dict):
        camps = camps.get('campaigns', camps.get('data', []))
    return camps


def find_wrong_person_campaign(camps: list, project: str) -> int:
    """
    Auto-discover WRONG-PERSON referral campaign in SmartLead.
    Matches campaign name containing project name + 'WRONG' + 'PERSON'.
    """
    project_upper = project.upper()
    for c in camps:
        name_upper = c.get('name', '').upper()
        if project_upper in name_upper and 'WRONG' in name_upper and 'PERSON' in name_upper:
            logger.info(f"Auto-discovered destination: {c['name']} (id={c['id']})")
            return c['id']
    return 0


def find_project_campaign_names(camps: list, project: str) -> list:
    """
    Find all campaign names belonging to a project by name match.
    Excludes the WRONG-PERSON campaign itself.
    """
    project_upper = project.upper()
    names = []
    for c in camps:
        name = c.get('name', '')
        name_upper = name.upper()
        if project_upper not in name_upper:
            continue
        # Exclude the WRONG-PERSON destination campaign
        if 'WRONG' in name_upper and 'PERSON' in name_upper:
            continue
        names.append(name)
    logger.info(f"Found {len(names)} source campaigns for project '{project}'")
    return names


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        connect_timeout=5
    )


def get_wrong_person_leads(campaign_names: list):
    """
    Get unprocessed Wrong Person leads from processed_replies.
    Searches by exact campaign names discovered from SmartLead.
    """
    if not campaign_names:
        logger.warning("No source campaigns to search")
        return []

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        query = """
            SELECT pr.id, pr.lead_email, pr.lead_first_name, pr.lead_last_name,
                   pr.lead_company, pr.campaign_name, pr.received_at
            FROM processed_replies pr
            WHERE pr.category = 'wrong_person'
              AND pr.campaign_name = ANY(%s)
              AND pr.lead_email IS NOT NULL
              AND pr.lead_email != ''
              AND NOT EXISTS (
                  SELECT 1 FROM contact_activities ca
                  WHERE ca.extra_data->>'processed_reply_id' = pr.id::text
                    AND ca.extra_data->>'smartlead_synced' = 'true'
              )
            ORDER BY pr.received_at DESC
            LIMIT 500
        """

        cur.execute(query, (campaign_names,))
        rows = cur.fetchall()
        cur.close()

        leads = []
        seen_emails = set()
        for row in rows:
            email = row['lead_email'].lower().strip()
            if email and email not in seen_emails:
                seen_emails.add(email)
                leads.append({
                    'email': email,
                    'first_name': row['lead_first_name'] or '',
                    'last_name': row['lead_last_name'] or '',
                    'company': row['lead_company'] or '',
                    'campaign': row['campaign_name'] or '',
                    'reply_id': row['id'],
                })

        return leads
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return []
    finally:
        if conn:
            conn.close()


def add_leads_to_smartlead(leads: list, campaign_id: int) -> dict:
    """
    Add leads to SmartLead campaign via direct API call.

    Sets custom field 'colleague_name' = lead's first_name.
    In Wrong Person flow, the lead in processed_replies IS the original
    contact who replied "wrong person". The sequence uses {{colleague_name}}
    to reference them: "I reached out to {{colleague_name}} - they pointed
    me to you."
    """
    if not leads:
        return {'added': 0, 'failed': 0, 'errors': []}

    if not SMARTLEAD_API_KEY:
        error = "SMARTLEAD_API_KEY not set in environment"
        logger.error(error)
        return {'added': 0, 'failed': len(leads), 'errors': [error]}

    lead_list = []
    for lead in leads:
        entry = {
            'email': lead['email'],
            'first_name': lead['first_name'] or lead['email'].split('@')[0],
            'last_name': lead.get('last_name', ''),
            'company_name': lead['company'] or '',
            'custom_fields': {
                'colleague_name': lead['first_name'] or '',
            }
        }
        lead_list.append(entry)

    try:
        response = httpx.post(
            f'{SMARTLEAD_BASE_URL}/campaigns/{campaign_id}/leads',
            params={'api_key': SMARTLEAD_API_KEY},
            json={'lead_list': lead_list},
            timeout=30
        )

        if response.status_code in [200, 201]:
            result = response.json()
            logger.info(f"SmartLead API response: {json.dumps(result, indent=2)[:500]}")

            added = 0
            failed = 0
            errors = []

            if isinstance(result, dict):
                added = result.get('upload_count', result.get('total', len(leads)))
                failed = result.get('failed_count', 0)
                if result.get('failed_leads'):
                    for fl in result['failed_leads'][:5]:
                        errors.append(f"{fl.get('email', '?')}: {fl.get('reason', '?')}")

            return {'added': added, 'failed': failed, 'errors': errors}
        else:
            error_msg = f"SmartLead API {response.status_code}: {response.text[:200]}"
            logger.error(error_msg)
            return {'added': 0, 'failed': len(leads), 'errors': [error_msg]}
    except Exception as e:
        error_msg = f"SmartLead API exception: {e}"
        logger.error(error_msg)
        return {'added': 0, 'failed': len(leads), 'errors': [error_msg]}


def mark_as_processed(reply_ids: list, campaign_id: int):
    """
    Mark processed_replies as synced in contact_activities.
    If a lead has no matching contact record, inserts a standalone tracking
    row with contact_id=0 to prevent re-processing.
    """
    if not reply_ids:
        return

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        marked = 0
        for reply_id in reply_ids:
            # Try to find matching contact
            cur.execute("""
                INSERT INTO contact_activities
                    (contact_id, activity_type, channel, source, extra_data,
                     activity_at, created_at, updated_at)
                SELECT c.id, 'category_updated', 'smartlead', 'sync_wrong_person',
                       json_build_object(
                           'processed_reply_id', %s::text,
                           'smartlead_synced', 'true',
                           'campaign_id', %s::text
                       )::json,
                       NOW(), NOW(), NOW()
                FROM contacts c
                JOIN processed_replies pr ON LOWER(c.email) = LOWER(pr.lead_email)
                WHERE pr.id = %s AND c.deleted_at IS NULL
                LIMIT 1
            """, (reply_id, str(campaign_id), reply_id))

            if cur.rowcount == 0:
                # No matching contact found - still mark as processed
                # to prevent duplicate SmartLead uploads on next run
                cur.execute("""
                    INSERT INTO contact_activities
                        (contact_id, activity_type, channel, source, extra_data,
                         activity_at, created_at, updated_at)
                    VALUES (
                        (SELECT MIN(id) FROM contacts WHERE deleted_at IS NULL),
                        'category_updated', 'smartlead', 'sync_wrong_person',
                        json_build_object(
                            'processed_reply_id', %s::text,
                            'smartlead_synced', 'true',
                            'campaign_id', %s::text,
                            'note', 'no_matching_contact'
                        )::json,
                        NOW(), NOW(), NOW()
                    )
                """, (reply_id, str(campaign_id)))

            marked += 1

        conn.commit()
        cur.close()
        logger.info(f"Marked {marked}/{len(reply_ids)} replies as processed")
    except Exception as e:
        logger.error(f"Error marking as processed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def send_telegram_notification(stats: dict, leads_count: int, project: str, campaign_id: int, chat_id: str):
    """Send execution report to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning("Telegram config missing, skipping notification")
        return

    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M UTC')
        message = (
            f"Wrong Person Sync Report - {timestamp}\n"
            f"\n"
            f"Project: {project}\n"
            f"Found: {leads_count} unprocessed Wrong Person replies\n"
            f"Added to SmartLead: {stats['added']}\n"
            f"Failed: {stats['failed']}\n"
            f"\n"
            f"Campaign ID: {campaign_id}"
        )
        if stats['errors']:
            message += "\n\nErrors:\n"
            for error in stats['errors'][:3]:
                message += f"  - {error[:100]}\n"

        response = httpx.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': message,
            },
            timeout=10
        )
        if response.status_code == 200:
            logger.info(f"Telegram notification sent to {chat_id}")
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")


def sync_project(project: str, campaign_id: int, campaign_names: list,
                  chat_id: str, dry_run: bool) -> dict:
    """Sync Wrong Person leads for a single project. Returns stats dict."""
    logger.info("=" * 60)
    logger.info(f"Syncing Wrong Person: {project}")
    logger.info(f"Destination campaign ID: {campaign_id}")
    logger.info(f"Source campaigns: {len(campaign_names)}")
    for name in campaign_names:
        logger.info(f"  - {name}")
    if dry_run:
        logger.info("DRY RUN - no changes will be made")
    logger.info("=" * 60)

    # 1. Get Wrong Person leads from source campaigns
    leads = get_wrong_person_leads(campaign_names)
    logger.info(f"Found {len(leads)} unprocessed Wrong Person replies")

    if not leads:
        logger.info("No leads to process")
        if not dry_run:
            send_telegram_notification({'added': 0, 'failed': 0, 'errors': []}, 0, project, campaign_id, chat_id)
        return {'project': project, 'found': 0, 'added': 0, 'failed': 0}

    # 2. Log what we found
    for lead in leads:
        logger.info(f"  {lead['email']} | {lead['first_name']} | {lead['company']} | from: {lead['campaign']}")

    if dry_run:
        logger.info(f"DRY RUN complete - {len(leads)} leads would be synced")
        return {'project': project, 'found': len(leads), 'added': 0, 'failed': 0}

    # 3. Add to SmartLead
    logger.info(f"Adding {len(leads)} leads to SmartLead campaign {campaign_id}...")
    stats = add_leads_to_smartlead(leads, campaign_id)
    logger.info(f"Result: added={stats['added']}, failed={stats['failed']}")

    # 4. Mark ALL fetched reply_ids as processed to prevent duplicates.
    # SmartLead silently skips existing emails (counts them as "added"),
    # so we mark everything that was sent to the API.
    if stats['added'] > 0:
        reply_ids = [lead['reply_id'] for lead in leads]
        mark_as_processed(reply_ids, campaign_id)

    # 5. Send notification
    send_telegram_notification(stats, len(leads), project, campaign_id, chat_id)

    return {'project': project, 'found': len(leads), 'added': stats['added'], 'failed': stats['failed']}


def main():
    parser = argparse.ArgumentParser(description='Sync Wrong Person replies to SmartLead campaign')
    parser.add_argument('--project', required=True,
                        help='Project name for campaign filter (e.g. OnSocial, EasyStaff)')
    parser.add_argument('--campaign-id', type=int, default=0,
                        help='SmartLead campaign ID (optional - auto-discovered if omitted)')
    parser.add_argument('--chat-id', required=True,
                        help='Telegram chat ID for notifications')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be synced without actually doing it')
    args = parser.parse_args()

    # Fetch all campaigns once
    camps = fetch_smartlead_campaigns()
    if not camps:
        logger.error("Failed to fetch campaigns from SmartLead")
        return

    # Find destination WRONG-PERSON campaign
    campaign_id = args.campaign_id
    if not campaign_id:
        campaign_id = find_wrong_person_campaign(camps, args.project)
        if not campaign_id:
            logger.error(f"No WRONG-PERSON campaign found for project '{args.project}'. "
                         f"Create a campaign named like c-{args.project}_WRONG-PERSON-referral "
                         f"or pass --campaign-id explicitly.")
            return

    # Find all source campaigns for this project (by name)
    campaign_names = find_project_campaign_names(camps, args.project)
    if not campaign_names:
        logger.warning(f"No source campaigns found for project '{args.project}'")

    sync_project(args.project, campaign_id, campaign_names, args.chat_id, args.dry_run)


if __name__ == '__main__':
    main()
