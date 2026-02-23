"""
Seed test replies for TEST_LORD_TEST project (id=43).
Creates realistic replies from pn@getsally.io with various categories
so the user can test the replies page UI.

Usage: cd backend && python seed_test_replies.py
"""
import asyncio
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from sqlalchemy import text


TEST_CAMPAIGNS = [
    {"name": "E2E_Test_GetSally_0220_0211", "campaign_id": "2954070", "lead_map_id": "2735068804"},
    {"name": "E2E_Test_Outreach_0220_0211", "campaign_id": "2954071", "lead_map_id": "2735068817"},
    {"name": "E2E_Test_Partnership_0220_0211", "campaign_id": "2954072", "lead_map_id": "2735068829"},
]
SMARTLEAD_LEAD_ID = "2916006166"
PROJECT_ID = 43

REPLIES = [
    # --- Campaign 1: E2E_Test_GetSally (2 replies, each with outbound+inbound thread) ---
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": TEST_CAMPAIGNS[0]["campaign_id"],
        "campaign_name": TEST_CAMPAIGNS[0]["name"],
        "source": "smartlead",
        "channel": "email",
        "email_subject": "Re: Partnership Opportunity with GetSally",
        "email_body": "Hi there,\n\nThanks for reaching out! I'm very interested in learning more about your solution. Could we schedule a call this week?\n\nBest,\nPetr",
        "reply_text": "Thanks for reaching out! I'm very interested in learning more about your solution. Could we schedule a call this week?",
        "category": "meeting_request",
        "category_confidence": "high",
        "classification_reasoning": "Lead explicitly requests a meeting/call to discuss further.",
        "draft_reply": "Hi Petr,\n\nThank you for your interest! I'd be happy to schedule a call this week. How does Thursday at 2pm CET work for you?\n\nLooking forward to connecting.\n\nBest regards",
        "draft_subject": "Re: Partnership Opportunity with GetSally",
        "received_at": datetime.utcnow() - timedelta(minutes=15),
        "thread": [
            {"direction": "outbound", "subject": "Partnership Opportunity with GetSally", "body": "Hi Petr,\n\nI noticed GetSally is growing fast in the sales automation space. We help companies like yours scale outreach by 3x.\n\nWould love to chat about a potential partnership. Got 15 minutes this week?\n\nBest,\nAlex", "offset_min": -60},
            {"direction": "inbound", "subject": "Re: Partnership Opportunity with GetSally", "body": "Hi there,\n\nThanks for reaching out! I'm very interested in learning more about your solution. Could we schedule a call this week?\n\nBest,\nPetr", "offset_min": -15},
        ],
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": TEST_CAMPAIGNS[0]["campaign_id"],
        "campaign_name": TEST_CAMPAIGNS[0]["name"],
        "source": "smartlead",
        "channel": "email",
        "email_subject": "Re: Quick question about your platform",
        "email_body": "Hey,\n\nThis looks interesting. Can you send me a case study or some examples of companies in our industry that use your product?\n\nThanks,\nPetr",
        "reply_text": "Can you send me a case study or some examples of companies in our industry that use your product?",
        "category": "interested",
        "category_confidence": "high",
        "classification_reasoning": "Lead shows interest and requests more information.",
        "draft_reply": "Hi Petr,\n\nAbsolutely! I've attached a case study from a company in your space that saw a 3x improvement in outreach efficiency using our platform.\n\nWould you like to walk through it together on a quick call?\n\nBest regards",
        "draft_subject": "Re: Quick question about your platform",
        "received_at": datetime.utcnow() - timedelta(minutes=30),
        "thread": [
            {"direction": "outbound", "subject": "Quick question about your platform", "body": "Hi Petr,\n\nJust following up on my earlier note. We recently launched a feature that integrates directly with CRM platforms like yours.\n\nCurious if you'd be open to seeing a quick demo?\n\nCheers,\nAlex", "offset_min": -90},
            {"direction": "inbound", "subject": "Re: Quick question about your platform", "body": "Hey,\n\nThis looks interesting. Can you send me a case study or some examples of companies in our industry that use your product?\n\nThanks,\nPetr", "offset_min": -30},
        ],
    },
    # --- Campaign 2: E2E_Test_Outreach (2 replies) ---
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": TEST_CAMPAIGNS[1]["campaign_id"],
        "campaign_name": TEST_CAMPAIGNS[1]["name"],
        "source": "smartlead",
        "channel": "email",
        "email_subject": "Re: Streamline your outreach",
        "email_body": "Hi,\n\nWhat's the pricing like? We're a team of 5 and currently using another tool. What would migration look like?\n\nPetr",
        "reply_text": "What's the pricing like? We're a team of 5 and currently using another tool. What would migration look like?",
        "category": "question",
        "category_confidence": "high",
        "classification_reasoning": "Lead asks specific questions about pricing and migration, indicating active evaluation.",
        "draft_reply": "Hi Petr,\n\nGreat questions! For a team of 5, our Growth plan at $99/mo would be perfect. Migration is seamless - we handle the import and setup for you, typically done in under 24 hours.\n\nWant me to set up a quick demo so you can see it in action?\n\nBest regards",
        "draft_subject": "Re: Streamline your outreach",
        "received_at": datetime.utcnow() - timedelta(hours=1),
        "thread": [
            {"direction": "outbound", "subject": "Streamline your outreach", "body": "Hi Petr,\n\nAre you tired of manually managing outreach sequences? Our platform automates email campaigns, follow-ups, and lead scoring.\n\nSave 10+ hours a week. Want to see how?\n\nBest,\nMaria", "offset_min": -180},
            {"direction": "outbound", "subject": "Re: Streamline your outreach", "body": "Hi Petr,\n\nJust bumping this in case it got buried. Happy to jump on a quick call to walk you through the platform.\n\nMaria", "offset_min": -120},
            {"direction": "inbound", "subject": "Re: Streamline your outreach", "body": "Hi,\n\nWhat's the pricing like? We're a team of 5 and currently using another tool. What would migration look like?\n\nPetr", "offset_min": -60},
        ],
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": TEST_CAMPAIGNS[1]["campaign_id"],
        "campaign_name": TEST_CAMPAIGNS[1]["name"],
        "source": "smartlead",
        "channel": "email",
        "email_subject": "Re: Collaboration opportunity",
        "email_body": "Not interested at this time, thanks.\n\nPetr",
        "reply_text": "Not interested at this time, thanks.",
        "category": "not_interested",
        "category_confidence": "high",
        "classification_reasoning": "Lead explicitly states they are not interested.",
        "draft_reply": "Hi Petr,\n\nNo problem at all! I appreciate you letting me know. If anything changes down the road, feel free to reach out.\n\nWishing you all the best.\n\nBest regards",
        "draft_subject": "Re: Collaboration opportunity",
        "received_at": datetime.utcnow() - timedelta(hours=2),
        "thread": [
            {"direction": "outbound", "subject": "Collaboration opportunity", "body": "Hi Petr,\n\nI came across GetSally and think there's a great collaboration opportunity between our teams. We work with similar customers and our tools complement each other.\n\nWould you be open to a quick exploratory call?\n\nBest,\nMaria", "offset_min": -240},
            {"direction": "inbound", "subject": "Re: Collaboration opportunity", "body": "Not interested at this time, thanks.\n\nPetr", "offset_min": -120},
        ],
    },
    # --- Campaign 3: E2E_Test_Partnership (2 replies) ---
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": TEST_CAMPAIGNS[2]["campaign_id"],
        "campaign_name": TEST_CAMPAIGNS[2]["name"],
        "source": "smartlead",
        "channel": "email",
        "email_subject": "Re: Automate your sales pipeline",
        "email_body": "Hi,\n\nI'm out of the office until February 25th with limited access to email. I'll get back to you when I return.\n\nBest,\nPetr",
        "reply_text": "I'm out of the office until February 25th with limited access to email. I'll get back to you when I return.",
        "category": "out_of_office",
        "category_confidence": "high",
        "classification_reasoning": "Automated out-of-office reply mentioning return date.",
        "draft_reply": None,
        "draft_subject": None,
        "received_at": datetime.utcnow() - timedelta(hours=3),
        "thread": [
            {"direction": "outbound", "subject": "Automate your sales pipeline", "body": "Hi Petr,\n\nManaging a growing sales pipeline manually is tough. Our AI-powered platform handles lead scoring, sequence automation, and CRM sync.\n\nLet me show you how we helped a similar-sized team close 40% more deals.\n\nBest,\nDaniel", "offset_min": -360},
            {"direction": "inbound", "subject": "Re: Automate your sales pipeline", "body": "Hi,\n\nI'm out of the office until February 25th with limited access to email. I'll get back to you when I return.\n\nBest,\nPetr", "offset_min": -180},
        ],
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": TEST_CAMPAIGNS[2]["campaign_id"],
        "campaign_name": TEST_CAMPAIGNS[2]["name"],
        "source": "smartlead",
        "channel": "email",
        "email_subject": "Re: Let's connect about lead generation",
        "email_body": "Sounds great! Let's do Wednesday at 11am. Here's my Calendly link: https://calendly.com/petr-nikolaev/30min\n\nCheers,\nPetr",
        "reply_text": "Sounds great! Let's do Wednesday at 11am. Here's my Calendly link.",
        "category": "meeting_request",
        "category_confidence": "high",
        "classification_reasoning": "Lead proposes a specific meeting time and shares scheduling link.",
        "draft_reply": "Hi Petr,\n\nPerfect! I've booked Wednesday at 11am through your Calendly. Looking forward to our chat!\n\nBest regards",
        "draft_subject": "Re: Let's connect about lead generation",
        "received_at": datetime.utcnow() - timedelta(minutes=5),
        "thread": [
            {"direction": "outbound", "subject": "Let's connect about lead generation", "body": "Hi Petr,\n\nI've been following GetSally's growth — impressive traction! We specialize in lead generation tools for SaaS companies.\n\nI think we could help you 2x your outbound pipeline. Got time for a quick chat?\n\nBest,\nDaniel", "offset_min": -30},
            {"direction": "inbound", "subject": "Re: Let's connect about lead generation", "body": "Sounds great! Let's do Wednesday at 11am. Here's my Calendly link: https://calendly.com/petr-nikolaev/30min\n\nCheers,\nPetr", "offset_min": -5},
        ],
    },
]


async def main():
    from app.db.database import async_session_maker
    from app.models.reply import ProcessedReply, ThreadMessage
    from app.models.contact import Project
    from sqlalchemy import select, update

    async with async_session_maker() as session:
        # 1. Update project campaign_filters to include all test campaigns
        result = await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )
        project = result.scalar_one_or_none()
        if not project:
            print(f"Project {PROJECT_ID} not found!")
            return

        campaign_names = [c["name"] for c in TEST_CAMPAIGNS]
        filters = list(project.campaign_filters or [])
        changed = False
        for cname in campaign_names:
            if cname not in filters:
                filters.append(cname)
                changed = True
        if changed:
            project.campaign_filters = list(filters)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(project, "campaign_filters")
            print(f"Updated project campaign_filters: {filters}")
        else:
            print(f"All campaign filters already present: {filters}")

        # 2. Delete existing test replies + their thread messages (cascade)
        existing = await session.execute(
            select(ProcessedReply).where(
                ProcessedReply.campaign_name.in_(campaign_names)
            )
        )
        old = existing.scalars().all()
        if old:
            for r in old:
                await session.delete(r)
            print(f"Deleted {len(old)} existing test replies (thread_messages cascade)")

        # Flush deletes before inserting new ones
        await session.flush()

        # 3. Create new test replies + thread messages
        total_threads = 0
        for i, data in enumerate(REPLIES):
            # Find the matching campaign's lead_map_id for inbox link
            camp_meta = next((c for c in TEST_CAMPAIGNS if c["campaign_id"] == data["campaign_id"]), None)
            lead_map_id = camp_meta["lead_map_id"] if camp_meta else None
            inbox_link = f"https://app.smartlead.ai/app/master-inbox?action=INBOX&leadMap={lead_map_id}" if lead_map_id else None

            reply = ProcessedReply(
                lead_email=data["lead_email"],
                lead_first_name=data["lead_first_name"],
                lead_last_name=data["lead_last_name"],
                lead_company=data["lead_company"],
                campaign_id=data["campaign_id"],
                campaign_name=data["campaign_name"],
                source=data["source"],
                channel=data["channel"],
                email_subject=data["email_subject"],
                email_body=data["email_body"],
                reply_text=data["reply_text"],
                category=data["category"],
                category_confidence=data["category_confidence"],
                classification_reasoning=data["classification_reasoning"],
                draft_reply=data["draft_reply"],
                draft_subject=data["draft_subject"],
                received_at=data["received_at"],
                processed_at=datetime.utcnow(),
                approval_status=None,  # NULL = shows as needs_reply
                sent_to_slack=False,
                thread_fetched_at=datetime.utcnow(),  # Prevent SmartLead re-fetch
                smartlead_lead_id=SMARTLEAD_LEAD_ID,
                inbox_link=inbox_link,
            )
            session.add(reply)
            await session.flush()  # Get reply.id for thread messages

            # Create thread messages for this reply
            for pos, msg in enumerate(data.get("thread", [])):
                tm = ThreadMessage(
                    reply_id=reply.id,
                    direction=msg["direction"],
                    channel="email",
                    subject=msg["subject"],
                    body=msg["body"],
                    activity_at=datetime.utcnow() + timedelta(minutes=msg["offset_min"]),
                    source="smartlead",
                    activity_type="email_sent" if msg["direction"] == "outbound" else "email_replied",
                    position=pos,
                )
                session.add(tm)
                total_threads += 1

            print(f"  [{i+1}] {data['category']:20s} | {data['campaign_name']:25s} | {len(data.get('thread', []))} msgs | {data['email_subject'][:40]}")

        await session.commit()
        print(f"\nCreated {len(REPLIES)} test replies + {total_threads} thread messages")
        print(f"Project: '{project.name}' (id={PROJECT_ID})")
        print(f"Campaigns ({len(TEST_CAMPAIGNS)}):")
        for c in TEST_CAMPAIGNS:
            count = sum(1 for r in REPLIES if r["campaign_name"] == c["name"])
            msgs = sum(len(r.get("thread", [])) for r in REPLIES if r["campaign_name"] == c["name"])
            print(f"  - {c['name']} ({count} replies, {msgs} thread messages)")
        print(f"\nView at: http://localhost:5179/replies?project=test_lord_test")


if __name__ == "__main__":
    asyncio.run(main())
