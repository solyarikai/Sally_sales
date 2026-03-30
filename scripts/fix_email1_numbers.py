#!/usr/bin/env python3
"""Fix Email 1 — realistic savings numbers."""
import asyncio
import sys
import os

sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

CID = '3042239'
BR = '<br>'
P = f'{BR}{BR}'


async def main():
    sl = SmartleadService()

    sequences = [
        {
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": "{{company_name}} — paying freelancers in Pakistan?",
            "email_body": (
                f"Hi {{{{first_name}}}},{P}"
                f"We at Easystaff help companies pay freelancers globally with "
                f"fees under 1% — zero fees for your freelancers.{P}"
                f"You can pay contractors via cards, PayPal, and USDT wallets — "
                f"all paperwork handled by us.{P}"
                f"Recently helped a UAE agency switch from Deel "
                f"to paying 50 Pakistani freelancers, saving them $3,000/month "
                f"on platform fees and exchange rates.{P}"
                f"Would you like to calculate the cost benefit for your case?{P}"
                f"Best regards,{BR}"
                f"Petr"
            ),
        },
        {
            "seq_number": 2,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "",
            "email_body": (
                f"Hi {{{{first_name}}}},{P}"
                f"Following up. Many companies we talk to are moving off Upwork "
                f"or are frustrated with Deel's inflexibility.{P}"
                f"We offer a better way:{BR}"
                f"- Cut out the middleman: Save the 10-20% freelance marketplace fees{BR}"
                f"- No annual contracts: Pay only for what you use{BR}"
                f"- Same-day payouts to any country, real human support (no bots){BR}"
                f"- One compliant B2B invoice for all freelancer payments{P}"
                f"Open to a quick demo call this week?"
            ),
        },
        {
            "seq_number": 3,
            "seq_delay_details": {"delay_in_days": 4},
            "subject": "",
            "email_body": (
                f"Hi {{{{first_name}}}},{P}"
                f"Just making sure my emails are getting through.{P}"
                f"Our pricing is transparent: from 3% or a flat $39 per task. "
                f"Free withdrawals for freelancers. Mass payouts via Excel upload.{P}"
                f"For 50+ contractors/month, we offer custom rates below any competitor.{P}"
                f"Can I send you a 2-minute walkthrough video?"
            ),
        },
        {
            "seq_number": 4,
            "seq_delay_details": {"delay_in_days": 7},
            "subject": "",
            "email_body": (
                f"Would it be easier to connect on LinkedIn or Telegram?{P}"
                f"Just a reminder, if you're already using a payment solution, "
                f"we can calculate the savings for you based on your current setup.{P}"
                f"Sent from my iPhone"
            ),
        },
        {
            "seq_number": 5,
            "seq_delay_details": {"delay_in_days": 7},
            "subject": "",
            "email_body": (
                f"Hi {{{{first_name}}}},{P}"
                f"I know you're busy and probably have a payment solution already.{P}"
                f"But many clients switch to us for better terms, real human support, "
                f"and fewer issues with global payouts compared to competitors' "
                f"rigid systems or hidden fees.{P}"
                f"If improving international payments is still a goal, I'm here to help.{P}"
                f"Best regards,{BR}"
                f"Petr"
            ),
        },
    ]

    result = await sl.set_campaign_sequences(CID, sequences)
    print(f"Updated: {result}")

    new_steps = await sl.get_campaign_sequences(CID)
    print(f"Verified: {len(new_steps)} steps")
    for s in new_steps:
        subj = s.get('subject', '') or '(reply thread)'
        print(f"  Step {s['seq_number']}: {subj[:50]}")

if __name__ == '__main__':
    asyncio.run(main())
