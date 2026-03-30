#!/usr/bin/env python3
"""Fix sequence formatting + remove rinat accounts from UAE-PK campaign."""
import asyncio
import httpx
import os
import sys

sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

SL_KEY = os.environ.get('SMARTLEAD_API_KEY', '')
BASE = 'https://server.smartlead.ai/api/v1'
CID = '3042239'

BR = '<br>'
P = f'{BR}{BR}'


async def main():
    sl = SmartleadService()

    # 1. Fix sequence with proper formatting + empty subjects for follow-ups
    print("=== Fixing sequence ===")
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
                f"Recently helped a UAE outsource agency switch from Deel "
                f"to paying 20 Pakistani freelancers, saving them $10k/month "
                f"on fees and exchange rates.{P}"
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
    print(f"Sequence set: {result}")

    steps = await sl.get_campaign_sequences(CID)
    for step in steps:
        seq = step.get('seq_number', '?')
        subj = step.get('subject', '') or '(empty — threads as reply)'
        print(f"  Step {seq}: subject='{subj[:50]}'")

    # 2. Remove rinat@ accounts, keep only petr@ accounts
    print("\n=== Removing rinat@ accounts ===")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{BASE}/campaigns/{CID}/email-accounts",
                       params={"api_key": SL_KEY})
        if r.status_code != 200:
            print(f"Error getting accounts: {r.status_code}")
            return

        accounts = r.json()
        print(f"Current accounts: {len(accounts)}")

        petr_count = 0
        rinat_count = 0
        for acc in accounts:
            email = acc.get('from_email', '')
            if 'rinat' in email.lower():
                # Remove rinat account from campaign
                acc_id = acc.get('id')
                r2 = await c.delete(
                    f"{BASE}/campaigns/{CID}/email-accounts/{acc_id}",
                    params={"api_key": SL_KEY}
                )
                rinat_count += 1
                await asyncio.sleep(0.3)
            else:
                petr_count += 1

        print(f"Kept: {petr_count} petr@ accounts")
        print(f"Removed: {rinat_count} rinat@ accounts")

        # Verify
        r3 = await c.get(f"{BASE}/campaigns/{CID}/email-accounts",
                        params={"api_key": SL_KEY})
        final = r3.json() if r3.status_code == 200 else []
        print(f"Final account count: {len(final)}")
        for acc in final[:5]:
            print(f"  {acc.get('from_email', '')}")
        if len(final) > 5:
            print(f"  ... and {len(final) - 5} more")

    print("\n=== Done ===")


if __name__ == '__main__':
    asyncio.run(main())
