"""Create demo user danila@getsally.io with EasyStaff RU data copied from main app.

Copies:
- Contacts with replies (last 3 months)
- Replies with drafts, categories, conversation history
- Campaigns matching EasyStaff RU
- All integrations (shared keys)

Run on Hetzner:
  docker exec mcp-backend python /app/scripts/create_danila_demo.py
"""
import asyncio
import sys
import os
import json
import hashlib
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

async def main():
    # ── Connect to BOTH databases ──
    import asyncpg

    # Use localhost ports (mapped by Docker)
    main_pool = await asyncpg.create_pool(
        "postgresql://leadgen:leadgen_secret@localhost:5432/leadgen",
        min_size=1, max_size=3,
    )
    mcp_pool = await asyncpg.create_pool(
        "postgresql://mcp:mcp_secret@localhost:5433/mcp_leadgen",
        min_size=1, max_size=3,
    )

    print("Connected to both databases")

    # ── 1. Create user danila ──
    existing = await mcp_pool.fetchrow("SELECT id FROM mcp_users WHERE email = 'danila@getsally.io'")
    if existing:
        user_id = existing["id"]
        print(f"User exists: id={user_id}")
    else:
        import bcrypt
        pw_hash = bcrypt.hashpw(b"qweqweqwe", bcrypt.gensalt()).decode()
        user_id = await mcp_pool.fetchval("""
            INSERT INTO mcp_users (email, name, password_hash, is_active)
            VALUES ('danila@getsally.io', 'Danila', $1, true) RETURNING id
        """, pw_hash)
        print(f"Created user: id={user_id}")

    # Generate API token
    import secrets
    raw_token = "mcp_" + secrets.token_hex(32)
    token_prefix = raw_token[:12]
    token_hash = bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()
    await mcp_pool.execute("""
        INSERT INTO mcp_api_tokens (user_id, token_prefix, token_hash, name, is_active)
        VALUES ($1, $2, $3, 'demo', true)
    """, user_id, token_prefix, token_hash)
    print(f"Token: {raw_token}")

    # ── 2. Create company ──
    company_id = await mcp_pool.fetchval("""
        INSERT INTO companies (name) VALUES ('EasyStaff Company')
        ON CONFLICT DO NOTHING RETURNING id
    """)
    if not company_id:
        company_id = await mcp_pool.fetchval("SELECT id FROM companies ORDER BY id DESC LIMIT 1")

    # ── 3. Create project "EasyStaff" ──
    # Get ICP from main app
    main_project = await main_pool.fetchrow("SELECT * FROM projects WHERE id = 40")

    existing_project = await mcp_pool.fetchrow("SELECT id FROM projects WHERE name = 'EasyStaff' AND user_id = $1", user_id)
    if existing_project:
        project_id = existing_project["id"]
        print(f"Project exists: id={project_id}")
    else:
        project_id = await mcp_pool.fetchval("""
            INSERT INTO projects (name, user_id, company_id, is_active, target_segments, target_industries,
                sender_name, sender_company, sender_position, campaign_filters)
            VALUES ('EasyStaff', $1, $2, true, $3, $4, $5, $6, $7, $8) RETURNING id
        """, user_id, company_id,
            main_project["target_segments"] if main_project else "Companies hiring freelancers/contractors globally",
            main_project["target_industries"] if main_project else "IT, SaaS, Fintech",
            "Danila Sokolov",
            "easystaff.io",
            "Partner",
            json.dumps(main_project["campaign_filters"]) if main_project and main_project["campaign_filters"] else "[]",
        )
        print(f"Created project: id={project_id}")

    # ── 4. Set up integrations (shared keys) ──
    # Simple encryption for storing keys (Fernet or just base64 — match what MCP expects)
    try:
        from app.services.encryption import encrypt_value
    except ImportError:
        # Running outside container — use simple base64
        import base64
        def encrypt_value(v):
            return base64.b64encode(v.encode()).decode()

    integrations = {
        "smartlead": "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5",
        "apollo": "9yIx2mZegixXHeDf6mWVqA",
        "openai": os.environ.get("OPENAI_API_KEY", ""),
    }
    for name, key in integrations.items():
        if not key:
            continue
        encrypted = encrypt_value(key)
        await mcp_pool.execute("""
            INSERT INTO mcp_integration_settings (user_id, integration_name, api_key_encrypted, is_connected, connection_info)
            VALUES ($1, $2, $3, true, $4)
            ON CONFLICT (user_id, integration_name) DO UPDATE SET api_key_encrypted = $3, is_connected = true, connection_info = $4
        """, user_id, name, encrypted, f"{name} connected")
    print(f"Integrations set up: {list(integrations.keys())}")

    # ── 5. Copy campaigns from main app ──
    main_campaigns = await main_pool.fetch("""
        SELECT DISTINCT campaign_name FROM processed_replies
        WHERE lead_email IN (SELECT email FROM contacts WHERE project_id = 40)
        AND campaign_name IS NOT NULL
    """)

    campaign_map = {}  # main campaign_name -> mcp campaign_id
    for mc in main_campaigns:
        cname = mc["campaign_name"]
        existing_camp = await mcp_pool.fetchrow("SELECT id FROM campaigns WHERE name = $1 AND project_id = $2", cname, project_id)
        if existing_camp:
            campaign_map[cname] = existing_camp["id"]
        else:
            cid = await mcp_pool.fetchval("""
                INSERT INTO campaigns (project_id, company_id, name, platform, status)
                VALUES ($1, $2, $3, 'smartlead', 'active') RETURNING id
            """, project_id, company_id, cname)
            campaign_map[cname] = cid
    print(f"Campaigns: {len(campaign_map)}")

    # ── 6. Copy contacts with replies (last 3 months) ──
    cutoff = datetime.utcnow() - timedelta(days=90)

    replied_contacts = await main_pool.fetch("""
        SELECT DISTINCT c.email, c.first_name, c.last_name, c.company_name, c.job_title,
            c.phone, c.linkedin_url, c.source, c.created_at,
            c.domain
        FROM contacts c
        JOIN processed_replies pr ON pr.lead_email = c.email
        WHERE c.project_id = 40 AND pr.received_at > $1
        LIMIT 500
    """, cutoff)

    contact_count = 0
    for rc in replied_contacts:
        existing_c = await mcp_pool.fetchrow(
            "SELECT id FROM extracted_contacts WHERE email = $1 AND project_id = $2",
            rc["email"], project_id
        )
        if existing_c:
            continue

        sd = {
            "campaign": rc.get("source") or "EasyStaff RU",
            "has_replied": True,
        }

        await mcp_pool.execute("""
            INSERT INTO extracted_contacts (project_id, email, first_name, last_name, job_title, phone, linkedin_url, email_source, source_data, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT DO NOTHING
        """, project_id, rc["email"], rc["first_name"], rc["last_name"],
            rc["job_title"], rc["phone"], rc["linkedin_url"],
            "smartlead", json.dumps(sd), rc["created_at"])
        contact_count += 1

    print(f"Contacts copied: {contact_count}")

    # ── 7. Copy replies with drafts ──
    replies = await main_pool.fetch("""
        SELECT pr.* FROM processed_replies pr
        JOIN contacts c ON c.email = pr.lead_email
        WHERE c.project_id = 40 AND pr.received_at > $1
        ORDER BY pr.received_at DESC
        LIMIT 2000
    """, cutoff)

    reply_count = 0
    for r in replies:
        msg_hash = hashlib.md5((r["reply_text"] or "")[:500].lower().encode()).hexdigest() if r["reply_text"] else None

        camp_id = campaign_map.get(r["campaign_name"])

        try:
            await mcp_pool.execute("""
                INSERT INTO mcp_replies (
                    project_id, campaign_id, lead_email, lead_name, lead_company,
                    campaign_name, campaign_external_id, source, channel,
                    email_subject, reply_text, received_at,
                    category, category_confidence, classification_reasoning,
                    draft_reply, draft_subject, draft_generated_at,
                    approval_status, needs_reply, message_hash, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12,
                    $13, $14, $15,
                    $16, $17, $18,
                    $19, $20, $21, $22
                ) ON CONFLICT DO NOTHING
            """,
                project_id, camp_id, r["lead_email"],
                f"{r['lead_first_name'] or ''} {r['lead_last_name'] or ''}".strip() or None,
                r["lead_company"],
                r["campaign_name"], str(r["campaign_id"]) if r["campaign_id"] else None,
                r["source"] or "smartlead", r["channel"] or "email",
                r["email_subject"], r["reply_text"], r["received_at"],
                r["category"], str(r["category_confidence"]) if r["category_confidence"] else None,
                r["classification_reasoning"],
                r["draft_reply"], r["draft_subject"], r["draft_generated_at"],
                r["approval_status"],
                r["category"] in ("interested", "meeting_request", "question", "other") if r["category"] else True,
                msg_hash, r["created_at"],
            )
            reply_count += 1
        except Exception as e:
            if "duplicate" not in str(e).lower():
                print(f"  Reply error: {e}")

    print(f"Replies copied: {reply_count}")

    # ── 8. Set user's active project ──
    await mcp_pool.execute("UPDATE mcp_users SET active_project_id = $1 WHERE id = $2", project_id, user_id)

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"DEMO USER CREATED")
    print(f"{'='*60}")
    print(f"Email: danila@getsally.io")
    print(f"Password: qweqweqwe")
    print(f"Token: {raw_token}")
    print(f"Project: EasyStaff (id={project_id})")
    print(f"Contacts: {contact_count}")
    print(f"Replies: {reply_count}")
    print(f"Campaigns: {len(campaign_map)}")
    print(f"Integrations: SmartLead, Apollo, OpenAI")
    print(f"\nLogin at: http://46.62.210.24:3000")
    print(f"{'='*60}")

    await main_pool.close()
    await mcp_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
