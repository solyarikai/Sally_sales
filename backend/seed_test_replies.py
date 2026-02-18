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


TEST_CAMPAIGN = "E2E_Test_GetSally"
SMARTLEAD_CAMPAIGN_ID = "2947079"  # Real SmartLead campaign
PROJECT_ID = 43

REPLIES = [
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": SMARTLEAD_CAMPAIGN_ID,
        "campaign_name": TEST_CAMPAIGN,
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
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": SMARTLEAD_CAMPAIGN_ID,
        "campaign_name": TEST_CAMPAIGN,
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
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": SMARTLEAD_CAMPAIGN_ID,
        "campaign_name": TEST_CAMPAIGN,
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
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": SMARTLEAD_CAMPAIGN_ID,
        "campaign_name": TEST_CAMPAIGN,
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
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": SMARTLEAD_CAMPAIGN_ID,
        "campaign_name": TEST_CAMPAIGN,
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
    },
    {
        "lead_email": "pn@getsally.io",
        "lead_first_name": "Petr",
        "lead_last_name": "Nikolaev",
        "lead_company": "GetSally",
        "campaign_id": SMARTLEAD_CAMPAIGN_ID,
        "campaign_name": TEST_CAMPAIGN,
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
    },
]


async def main():
    from app.db.database import async_session_maker
    from app.models.reply import ProcessedReply
    from app.models.contact import Project
    from sqlalchemy import select, update

    async with async_session_maker() as session:
        # 1. Update project campaign_filters to include our test campaign
        result = await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )
        project = result.scalar_one_or_none()
        if not project:
            print(f"Project {PROJECT_ID} not found!")
            return

        filters = list(project.campaign_filters or [])
        if TEST_CAMPAIGN not in filters:
            filters.append(TEST_CAMPAIGN)
            # Must assign a NEW list for SQLAlchemy JSON mutation tracking
            project.campaign_filters = list(filters)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(project, "campaign_filters")
            print(f"Added '{TEST_CAMPAIGN}' to project campaign_filters: {filters}")
        else:
            print(f"Campaign filter already present: {filters}")

        # 2. Delete existing test replies for this campaign (clean slate)
        existing = await session.execute(
            select(ProcessedReply).where(
                ProcessedReply.campaign_name == TEST_CAMPAIGN
            )
        )
        old = existing.scalars().all()
        if old:
            for r in old:
                await session.delete(r)
            print(f"Deleted {len(old)} existing test replies")

        # 3. Create new test replies
        for i, data in enumerate(REPLIES):
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
            )
            session.add(reply)
            print(f"  [{i+1}] {data['category']:20s} | {data['email_subject'][:50]}")

        await session.commit()
        print(f"\nCreated {len(REPLIES)} test replies for project '{project.name}' (id={PROJECT_ID})")
        print(f"Campaign: {TEST_CAMPAIGN}")
        print(f"\nView at: http://localhost:5179/replies (select project TEST_LORD_TEST)")


if __name__ == "__main__":
    asyncio.run(main())
