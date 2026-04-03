#!/usr/bin/env python3
"""Set sequence on UAE-PK campaign 3048388.
v3: Same style as 3043938 but geography-neutral (not Pakistan-specific).
Don't sell the problem — trust examples, let them recognize it."""
import asyncio
import sys
import os

sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

CID = '3048388'


async def main():
    sl = SmartleadService()

    sequences = [
        {
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": "{{first_name}} \u2013 paying freelancers abroad?",
            "email_body": """Hi {{first_name}},

We at Easystaff help companies pay freelancers globally with fees under 1% \u2013 zero fees for your freelancers.

You can pay contractors via cards, PayPal, and USDT wallets \u2013 all paperwork handled by us.

Recently helped a UAE agency switch from Deel to paying 50 contractors across 8 countries, saving them $3,000/month on platform fees and exchange rates.

Would you like to calculate the cost benefit for your case?

Petr Nikolaev
BDM, Easystaff
Trusted by 5,000+ teams worldwide"""
        },
        {
            "seq_number": 2,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "",
            "email_body": """Hi {{first_name}},

Following up. Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility.

We offer a better way:
- Cut out the middleman: Save the 10-20% freelance marketplace fees
- No annual contracts: Pay only for what you use
- Same-day payouts to any country, real human support (no bots)
- One compliant B2B invoice for all freelancer payments

Open to a quick demo call this week?"""
        },
        {
            "seq_number": 3,
            "seq_delay_details": {"delay_in_days": 4},
            "subject": "",
            "email_body": """Hi {{first_name}},

Just making sure my emails are getting through.

Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.

For 50+ contractors/month, we offer custom rates below any competitor.

Can I send you a 2-minute walkthrough video?"""
        },
        {
            "seq_number": 4,
            "seq_delay_details": {"delay_in_days": 7},
            "subject": "",
            "email_body": """Would it be easier to connect on LinkedIn or Telegram?

If you already have a payment solution, happy to compare \u2013 many clients switch after seeing the total cost difference.

Sent from my iPhone"""
        },
        {
            "seq_number": 5,
            "seq_delay_details": {"delay_in_days": 7},
            "subject": "",
            "email_body": """Hi {{first_name}},

I know you're busy and probably have a payment solution already.

But many clients switch to us for better terms, real human support, and fewer issues with global payouts compared to competitors' rigid systems or hidden fees.

If improving international payments is still a goal, I'm here to help.

Petr Nikolaev
BDM, Easystaff
Trusted by 5,000+ teams worldwide"""
        },
    ]

    result = await sl.set_campaign_sequences(CID, sequences)
    print(f"Sequence set: {result}")

    steps = await sl.get_campaign_sequences(CID)
    print(f"Verified: {len(steps)} steps")
    for s in steps:
        seq = s.get('seq_number', '?')
        subj = s.get('subject', '') or '(reply thread)'
        delay = s.get('seq_delay_details', {})
        print(f"  Step {seq}: delay={delay} subject='{subj[:50]}'")


if __name__ == '__main__':
    asyncio.run(main())
