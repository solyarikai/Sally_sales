#!/usr/bin/env python3
"""Set the 5-email sequence on UAE-Pakistan SmartLead campaign."""
import asyncio
import sys
import os

sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

CAMPAIGN_ID = '3042239'


async def main():
    sl = SmartleadService()

    sequences = [
        {
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": "{{company_name}} — paying freelancers in Pakistan?",
            "email_body": """Hi {{first_name}},

We at Easystaff help companies pay freelancers globally with fees under 1% — zero fees for your freelancers.

You can pay contractors via cards, PayPal, and USDT wallets — all paperwork handled by us.

Recently helped a UAE outsource agency switch from Deel to paying 20 Pakistani freelancers, saving them $10k/month on fees and exchange rates.

Would you like to calculate the cost benefit for your case?

Best regards,
Petr"""
        },
        {
            "seq_number": 2,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "RE: {{company_name}} — paying freelancers in Pakistan?",
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
            "subject": "RE: {{company_name}} — paying freelancers in Pakistan?",
            "email_body": """Hi {{first_name}},

Just making sure my emails are getting through.

Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.

For 50+ contractors/month, we offer custom rates below any competitor.

Can I send you a 2-minute walkthrough video?"""
        },
        {
            "seq_number": 4,
            "seq_delay_details": {"delay_in_days": 7},
            "subject": "RE: {{company_name}} — paying freelancers in Pakistan?",
            "email_body": """Would it be easier to connect on LinkedIn or Telegram?

Just a reminder, if you're already using a payment solution, we can calculate the savings for you based on your current setup.

Sent from my iPhone"""
        },
        {
            "seq_number": 5,
            "seq_delay_details": {"delay_in_days": 7},
            "subject": "RE: {{company_name}} — paying freelancers in Pakistan?",
            "email_body": """Hi {{first_name}},

I know you're busy and probably have a payment solution already.

But many clients switch to us for better terms, real human support, and fewer issues with global payouts compared to competitors' rigid systems or hidden fees.

If improving international payments is still a goal, I'm here to help.

Best regards,
Petr"""
        },
    ]

    print(f"Setting 5-email sequence on campaign {CAMPAIGN_ID}...")
    result = await sl.set_campaign_sequences(CAMPAIGN_ID, sequences)
    print(f"Result: {result}")

    # Verify
    steps = await sl.get_campaign_sequences(CAMPAIGN_ID)
    print(f"\nVerification — {len(steps)} steps set:")
    for step in steps:
        seq = step.get('seq_number', '?')
        subj = step.get('subject', '')[:60]
        delay = step.get('seq_delay_details', {})
        print(f"  Step {seq}: delay={delay} subject='{subj}'")


if __name__ == '__main__':
    asyncio.run(main())
