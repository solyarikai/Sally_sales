#!/usr/bin/env python3
"""Fix AU-PH campaign 3057831 sequence — use HTML line breaks."""
import asyncio
import sys
sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

CID = '3057831'

SEQUENCES = [
    {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "{{first_name}} \u2013 paying freelancers abroad?",
        "email_body": (
            "Hi {{first_name}},<br><br>"
            "We at Easystaff help companies pay freelancers globally with fees under 1% \u2013 zero fees for your freelancers.<br><br>"
            "You can pay contractors via cards, PayPal, and USDT wallets \u2013 all paperwork handled by us.<br><br>"
            "Recently helped a company in {{city}} switch from Deel to paying 50 contractors across 8 countries, saving them $3,000/month on platform fees and exchange rates.<br><br>"
            "Would you like to calculate the cost benefit for your case?<br><br>"
            "Petr Nikolaev<br>"
            "BDM, Easystaff<br>"
            "Trusted by 5,000+ teams worldwide"
        ),
    },
    {
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "",
        "email_body": (
            "Hi {{first_name}},<br><br>"
            "Following up. Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility.<br><br>"
            "We offer a better way:<br>"
            "- Cut out the middleman: Save the 10-20% freelance marketplace fees<br>"
            "- No annual contracts: Pay only for what you use<br>"
            "- Same-day payouts to any country, real human support (no bots)<br>"
            "- One compliant B2B invoice for all freelancer payments<br><br>"
            "Open to a quick demo call this week?"
        ),
    },
    {
        "seq_number": 3,
        "seq_delay_details": {"delay_in_days": 4},
        "subject": "",
        "email_body": (
            "Hi {{first_name}},<br><br>"
            "Just making sure my emails are getting through.<br><br>"
            "Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.<br><br>"
            "For 50+ contractors/month, we offer custom rates below any competitor.<br><br>"
            "Can I send you a 2-minute walkthrough video?"
        ),
    },
    {
        "seq_number": 4,
        "seq_delay_details": {"delay_in_days": 7},
        "subject": "",
        "email_body": (
            "Would it be easier to connect on LinkedIn or Telegram?<br><br>"
            "If you already have a payment solution, happy to compare \u2013 many clients switch after seeing the total cost difference.<br><br>"
            "Sent from my iPhone"
        ),
    },
    {
        "seq_number": 5,
        "seq_delay_details": {"delay_in_days": 7},
        "subject": "",
        "email_body": (
            "Hi {{first_name}},<br><br>"
            "I know you're busy and probably have a payment solution already.<br><br>"
            "But many clients switch to us for better terms, real human support, and fewer issues with global payouts compared to competitors' rigid systems or hidden fees.<br><br>"
            "If improving international payments is still a goal, I'm here to help.<br><br>"
            "Petr Nikolaev<br>"
            "BDM, Easystaff<br>"
            "Trusted by 5,000+ teams worldwide"
        ),
    },
]


async def main():
    sl = SmartleadService()
    result = await sl.set_campaign_sequences(CID, SEQUENCES)
    print(f"Sequence set: {result}")

    steps = await sl.get_campaign_sequences(CID)
    print(f"Verified: {len(steps)} steps")
    for s in steps:
        seq = s.get('seq_number', '?')
        subj = s.get('subject', '') or '(reply thread)'
        print(f"  Step {seq}: subject='{subj[:50]}'")


if __name__ == '__main__':
    asyncio.run(main())
