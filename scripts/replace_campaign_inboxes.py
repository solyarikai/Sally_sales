"""
Replace email inboxes in 3 Petr ES campaigns with Stanislav's Eleonora accounts.
Update sender name to "Eleonora Shcherbakova".
Send test email to pn@getsally.io.

Campaigns: Petr ES LatAm-Africa (3070920), Petr ES US-East (3070912), Petr ES UK-EU (3070915)

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && docker exec leadgen-backend \
    python -m scripts.replace_campaign_inboxes"
"""
import asyncio
import os
import httpx

API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BASE = "https://server.smartlead.ai/api/v1"

CAMPAIGNS = {
    "Petr ES LatAm-Africa": "3070920",
    "Petr ES US-East": "3070912",
    "Petr ES UK-EU": "3070915",
}

# Stanislav's Eleonora accounts from Google Sheet
STANISLAV_EMAILS = [
    "eleonora.s@easystaff-system.com",
    "eleonora.s@use-squarefi.com",
    "eleonora.s@solutioneasystaff.com",
    "eleonora@easystaff-solution.com",
    "eleonora@solutioneasystaff.com",
    "eleonora.s@platform-easystaff.com",
    "eleonora@easystaff-operations.com",
    "eleonora@floweasystaff.com",
    "eleonora@platform-easystaff.com",
    "eleonora.s@easystaff-ops.com",
    "eleonora.s@easystaffops.com",
    "eleonora.s@hire-easystaff.com",
    "eleonora.s@hireeasystaff.com",
    "eleonora.s@ops-easystaff.com",
    "eleonora.s@opseasystaff.com",
    "eleonora.s@try-easystaff.com",
    "eleonora.s@tryeasystaff.com",
    "eleonora.s@work-easystaff.com",
    "eleonora.s@workeasystaff.com",
    "eleonora@easystaff-ops.com",
    "eleonora@easystaffops.com",
    "eleonora@hire-easystaff.com",
    "eleonora@hireeasystaff.com",
    "eleonora@ops-easystaff.com",
    "eleonora@opseasystaff.com",
    "eleonora@try-easystaff.com",
    "eleonora@tryeasystaff.com",
    "eleonora@work-easystaff.com",
    "eleonora@workeasystaff.com",
    "eleonora.s@easystaff-payrolls.com",
    "eleonora.s@easystaff-transfer.com",
    "eleonora.s@easystaff-transfers.com",
    "eleonora.s@easystafffunds.com",
    "eleonora.s@easystaffpaycenter.com",
    "eleonora.s@easystaffpaydesk.com",
    "eleonora.s@easystaffpayhub.com",
    "eleonora.s@easystaffpayouts.com",
    "eleonora.s@easystaffpayrolls.com",
    "eleonora.s@easystafftransfer.com",
    "eleonora@transfers-easystaff.com",
    "eleonora@transferseasystaff.com",
]

SENDER_NAME = "Eleonora Shcherbakova"


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Get all SmartLead email accounts to find IDs
        print("=== Fetching SmartLead email accounts ===")
        resp = await client.get(f"{BASE}/email-accounts", params={"api_key": API_KEY, "offset": 0, "limit": 500})
        resp.raise_for_status()
        all_accounts = resp.json()
        print(f"Found {len(all_accounts)} total email accounts in SmartLead")

        # Map email -> account_id for Stanislav's accounts
        stanislav_accounts = {}
        for acc in all_accounts:
            email = acc.get("from_email", "")
            if email in STANISLAV_EMAILS:
                stanislav_accounts[email] = acc["id"]

        print(f"Found {len(stanislav_accounts)} of {len(STANISLAV_EMAILS)} Stanislav accounts in SmartLead")
        if len(stanislav_accounts) < 5:
            print("WARNING: Very few Stanislav accounts found. Listing what was found:")
            for email, aid in stanislav_accounts.items():
                print(f"  {email} -> {aid}")

        stanislav_account_ids = list(stanislav_accounts.values())

        for campaign_name, campaign_id in CAMPAIGNS.items():
            print(f"\n=== Processing: {campaign_name} (ID: {campaign_id}) ===")

            # Step 2: Get current email accounts for this campaign
            resp = await client.get(
                f"{BASE}/campaigns/{campaign_id}/email-accounts",
                params={"api_key": API_KEY}
            )
            resp.raise_for_status()
            current_accounts = resp.json()
            current_ids = [a["id"] for a in current_accounts] if isinstance(current_accounts, list) else []
            print(f"  Current accounts: {len(current_ids)}")

            # Step 3: Remove current accounts
            if current_ids:
                for acc_id in current_ids:
                    try:
                        resp = await client.post(
                            f"{BASE}/campaigns/{campaign_id}/email-accounts/remove",
                            params={"api_key": API_KEY},
                            json={"email_account_id": acc_id}
                        )
                        if resp.status_code == 200:
                            print(f"  Removed account {acc_id}")
                        else:
                            print(f"  Failed to remove {acc_id}: {resp.status_code} {resp.text[:200]}")
                    except Exception as e:
                        print(f"  Error removing {acc_id}: {e}")

            # Step 4: Add Stanislav's accounts
            print(f"  Adding {len(stanislav_account_ids)} Stanislav accounts...")
            resp = await client.post(
                f"{BASE}/campaigns/{campaign_id}/email-accounts",
                params={"api_key": API_KEY},
                json={"email_account_ids": stanislav_account_ids}
            )
            if resp.status_code == 200:
                print(f"  Added {len(stanislav_account_ids)} accounts")
            else:
                print(f"  Failed to add accounts: {resp.status_code} {resp.text[:200]}")

            # Step 5: Update sender name on each account for this campaign
            for acc_id in stanislav_account_ids:
                try:
                    resp = await client.post(
                        f"{BASE}/email-accounts/{acc_id}/update",
                        params={"api_key": API_KEY},
                        json={"from_name": SENDER_NAME}
                    )
                except Exception:
                    pass  # Some may fail if already set

            # Step 6: Update sequence signature to Eleonora
            resp = await client.get(
                f"{BASE}/campaigns/{campaign_id}/sequences",
                params={"api_key": API_KEY}
            )
            if resp.status_code == 200:
                sequences = resp.json()
                updated_seqs = []
                for seq in sequences:
                    body = seq.get("email_body", "")
                    # Replace Petr Nikolaev signature with Eleonora Shcherbakova
                    body = body.replace("Petr Nikolaev", SENDER_NAME)
                    body = body.replace("Petr", "Eleonora")
                    updated_seqs.append({
                        "seq_number": seq["seq_number"],
                        "seq_delay_details": seq.get("seq_delay_details", {"delay_in_days": 0}),
                        "subject": seq.get("subject", ""),
                        "email_body": body,
                    })

                resp = await client.post(
                    f"{BASE}/campaigns/{campaign_id}/sequences",
                    params={"api_key": API_KEY},
                    json=updated_seqs,
                )
                if resp.status_code == 200:
                    print(f"  Updated sequences with Eleonora signature")
                else:
                    print(f"  Failed to update sequences: {resp.status_code} {resp.text[:200]}")

            print(f"  Done: {campaign_name}")

        # Step 7: Send test emails to pn@getsally.io
        print("\n=== Sending test emails ===")
        for campaign_name, campaign_id in CAMPAIGNS.items():
            resp = await client.post(
                f"{BASE}/campaigns/{campaign_id}/send-test-email",
                params={"api_key": API_KEY},
                json={"email": "pn@getsally.io"}
            )
            if resp.status_code == 200:
                print(f"  Test email sent for {campaign_name}")
            else:
                print(f"  Test email failed for {campaign_name}: {resp.status_code} {resp.text[:200]}")

        print("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
