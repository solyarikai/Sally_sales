"""Fetch all conversations from SmartLead & GetSales for qualified/warm leads.

Run on Hetzner: docker exec leadgen-backend python /app/sofia/fetch_conversations.py
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, "/app")

from sqlalchemy import select, or_, func, text
from sqlalchemy.orm import selectinload


async def main():
    from app.db.database import async_session_maker
    from app.models.reply import ProcessedReply, ThreadMessage

    # All leads from the Google Sheet (email replies + LI replies)
    # We fetch ALL to get full picture, then filter warm/qualified in analysis
    sheet_emails = [
        "jay.richards@disruptmarketing.co", "dvalverde@flymetothemoon.es",
        "jhartnett@chartbeat.com", "melina.lee@nonsensical.agency",
        "rob.parkin@pulsarplatform.com", "ar@skeepers.io", "paul@duel.tech",
        "marlaina@htcollective.com", "darren.loveday@mention-me.com",
        "nathalie.strid@tourn.com", "solomon@growi.io", "bronson@luxelatam.com",
        "gustaf@mondsteinmedia.com", "colby@brighterclick.com",
        "daniel.schotland@linqia.com", "eviteri@publifyer.com",
        "luke.christison@mindshareworld.com", "nicke@pfrgroup.com",
        "tom.disapia@mindshareworld.com", "alan.weetch@mindshareworld.com",
        "alison.bringe@launchmetrics.com", "naida.hutchinson@mindshareworld.com",
        "lisa@beinfluence.eu", "hannah.feng@impact.com", "alex@infludata.com",
        "gilles@beinfluence.eu", "nj@buzzanova.dk", "lina@unitedinfluencers.se",
        "roland@styleranking.de", "allegra.kadet@neomediaworld.com",
        "jonathan@infludata.com", "sebastian@tourn.com",
        "jennifer@refluenced.com", "marwan@aidem-agency.com",
        "claudio@praytellagency.com", "stuart.hood@havasred.com",
        "kate.smailes@havas.com", "jacob@kjmarketingsweden.com",
        "ari@milkyway-agency.com", "berenice@grupo-go.es",
        "denis@m1rai.com", "gordon@gordonglenister.com",
        "melker@brandnation.se", "georg@gamesforest.club",
        "alyssa@spinbrands.co.uk", "nader@linqia.com",
        "martin.tollde@bizkithavas.se", "niklas.wallenberg@makeyourmark.se",
        "lindsey@thedigitaldept.com", "urban@influee.co",
        "jgoetz@webershandwick.com", "mstratton@webershandwick.com",
        "egladwin@webershandwick.com", "christiana@flightstory.com",
        "ernest@runwayinfluence.com", "yunus@yagency.dk",
        "dave.burke@impact.com", "ollie.richardson@omg.com",
        "ldarwin@webershandwick.com", "dominique@loudpixels.se",
        "salvador@grg.co", "fturner@webershandwick.com",
        "wroberts@webershandwick.com", "amelia.pierre@havasedge.fr",
        "atul@theshelf.com", "emily@socialmediaexaminer.com",
        "tivadar@medialabel.de", "arnab@peersway.com",
        "candace@creatororigin.com", "williamj@fanstories.com",
        "daniele.cicini@rosasagency.com", "mike@evolvez.co",
        "dan.walker@croud.com", "sergio@twic.es",
        "ourhai.tower@havasred.com", "sab@buzzanova.dk",
        "johan@impact.com", "georg@gameinfluencer.com",
        # LI replies (by email where available)
        "t.dorohova.minds@gmail.com", "keith.widerski@gmail.com",
        "cmollermolina@gmail.com", "louisdusartel@gmail.com",
        "chad@viralmedia.studio",
    ]

    results = {"conversations": [], "stats": {}}

    async with async_session_maker() as session:
        # 1. Fetch all processed_replies for these leads with thread messages
        stmt = (
            select(ProcessedReply)
            .options(selectinload(ProcessedReply.thread_messages))
            .where(
                func.lower(ProcessedReply.lead_email).in_([e.lower() for e in sheet_emails])
            )
            .order_by(ProcessedReply.received_at)
        )
        res = await session.execute(stmt)
        replies = res.scalars().all()

        print(f"Found {len(replies)} processed replies for sheet leads")

        # 2. Also fetch ALL replies with categories interested/meeting_request/question
        # (warm leads that might not be in the sheet)
        stmt2 = (
            select(ProcessedReply)
            .options(selectinload(ProcessedReply.thread_messages))
            .where(
                ProcessedReply.category.in_(["interested", "meeting_request", "question"])
            )
            .order_by(ProcessedReply.received_at)
        )
        res2 = await session.execute(stmt2)
        warm_replies = res2.scalars().all()
        print(f"Found {len(warm_replies)} warm/qualified replies (interested/meeting_request/question)")

        # Merge, deduplicate by id
        all_replies_map = {}
        for r in list(replies) + list(warm_replies):
            all_replies_map[r.id] = r

        # 3. Also fetch ALL replies (for full category distribution analysis)
        stmt3 = (
            select(ProcessedReply)
            .options(selectinload(ProcessedReply.thread_messages))
            .order_by(ProcessedReply.received_at)
        )
        res3 = await session.execute(stmt3)
        all_system_replies = res3.scalars().all()
        print(f"Found {len(all_system_replies)} total replies in system")

        # Build output for ALL replies (we need full picture for categorization)
        for r in all_system_replies:
            thread = []
            for msg in sorted(r.thread_messages, key=lambda m: m.position):
                thread.append({
                    "direction": msg.direction,
                    "channel": msg.channel,
                    "subject": msg.subject,
                    "body": msg.body,
                    "activity_at": msg.activity_at.isoformat() if msg.activity_at else None,
                    "activity_type": msg.activity_type,
                    "position": msg.position,
                })

            conv = {
                "reply_id": r.id,
                "lead_email": r.lead_email,
                "lead_name": f"{r.lead_first_name or ''} {r.lead_last_name or ''}".strip(),
                "lead_company": r.lead_company,
                "source": r.source,
                "channel": r.channel,
                "campaign_name": r.campaign_name,
                "category": r.category,
                "category_confidence": r.category_confidence,
                "classification_reasoning": r.classification_reasoning,
                "reply_text": r.reply_text or r.email_body,
                "email_subject": r.email_subject,
                "draft_reply": r.draft_reply,
                "draft_subject": r.draft_subject,
                "approval_status": r.approval_status,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "detected_language": r.detected_language,
                "translated_body": r.translated_body,
                "thread_messages": thread,
                "is_sheet_lead": r.lead_email and r.lead_email.lower() in [e.lower() for e in sheet_emails],
                "is_warm": r.category in ("interested", "meeting_request", "question"),
            }
            results["conversations"].append(conv)

        # Stats
        from collections import Counter
        cat_counts = Counter(r.category for r in all_system_replies)
        source_counts = Counter(r.source for r in all_system_replies)
        channel_counts = Counter(r.channel for r in all_system_replies)
        approval_counts = Counter(r.approval_status for r in all_system_replies)

        results["stats"] = {
            "total_replies": len(all_system_replies),
            "sheet_leads_found": len(replies),
            "warm_qualified": len(warm_replies),
            "by_category": dict(cat_counts),
            "by_source": dict(source_counts),
            "by_channel": dict(channel_counts),
            "by_approval": dict(approval_counts),
        }

    # Write output
    output_path = "/app/sofia/conversations_export.json"
    with open(output_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nExport saved to {output_path}")
    print(f"Stats: {json.dumps(results['stats'], indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
