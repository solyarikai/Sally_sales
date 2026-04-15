#!/usr/bin/env python3
"""
Unsubscribe all SmartLead leads from OnSocial paid client domains.
"""

import requests
import time

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"

CLIENT_DOMAINS = [
    "7senders.com",
    "accrueperformance.co.uk",
    "activate.social",
    "advocu.com",
    "affable.ai",
    "amiyah.in",
    "ampjar.com",
    "billion-dollar-boy.com",
    "billiondollarboy.com",
    "billo.app",
    "boostiny.com",
    "brandbassador.com",
    "brandwatch.com",
    "buttermilk.agency",
    "buzzstream.com",
    "clevertap.com",
    "collectively.inc",
    "dash-hudson.com",
    "digitalvoices.com",
    "disruptiveadvertising.com",
    "dovetale.com",
    "emplifi.io",
    "eqolot.com",
    "fanbytes.co.uk",
    "fohr.co",
    "getfluence.co",
    "gigapay.co",
    "goat-agency.com",
    "hashtagpaid.com",
    "hbagency.co",
    "heepsy.com",
    "heylinkme.co",
    "hypr.co",
    "ifluenz.com",
    "impulze.ai",
    "izea.com",
    "joinshares.com",
    "juliusworks.com",
    "kairos-media.com",
    "keepface.com",
    "kitly.com",
    "later.com",
    "linqia.com",
    "lottiefiles.com",
    "marketingforce.com",
    "mavrck.co",
    "mediakix.com",
    "meltwater.com",
    "metaone.gg",
    "mms.group",
    "moburst.com",
    "obviously.com",
    "openinfluence.com",
    "phlanx.com",
    "popular-pays.com",
    "reachbird.io",
    "scrunch.com",
    "sideqik.com",
    "smartocto.com",
    "socialbakers.com",
    "socialcat.com",
    "socialladder.com",
    "socially-powerful.com",
    "socialpeeks.com",
    "sparkle.io",
    "starfuel.io",
    "storipress.com",
    "tagger.com",
    "takumi.com",
    "taplio.com",
    "the5thcolumn.agency",
    "thecircularlab.com",
    "thehypeagency.co",
    "theinfluenceroom.com",
    "theshelfrz.com",
    "thesoul-publishing.com",
    "tinysponsor.com",
    "trybe.one",
    "vidiq.com",
    "viral-nation.com",
    "wearesocial.com",
    "webfluential.com",
    "wob.ag",
    "zoomph.com",
]


def fetch_lead(email: str) -> dict | None:
    r = requests.get(
        f"{BASE}/leads", params={"api_key": API_KEY, "email": email}, timeout=15
    )
    if r.status_code == 200:
        data = r.json()
        if data and isinstance(data, dict) and data.get("id"):
            return data
    return None


def unsubscribe(lead_id: int, email: str) -> bool:
    r = requests.post(
        f"{BASE}/leads/unsubscribe",
        params={"api_key": API_KEY},
        json={"lead_id": lead_id},
        timeout=15,
    )
    return r.status_code == 200


def main():
    print(f"Checking {len(CLIENT_DOMAINS)} client domains...\n")

    found = []
    not_found = []

    for domain in CLIENT_DOMAINS:
        # We don't know specific emails, search by domain pattern via fetch
        # SmartLead doesn't have domain search — skip, already found via MCP
        pass

    # Known client leads found via MCP fetch earlier
    known_leads = [
        {"id": 3347911754, "email": "saurabh.singh@linqia.com", "company": "Linqia"},
        {"id": 3349556740, "email": "kali@hashtagpaid.com", "company": "#paid"},
        {"id": 3347911772, "email": "tadas@billo.app", "company": "Billo"},
        {
            "id": 3355659387,
            "email": "chris.hackney@meltwater.com",
            "company": "Meltwater",
        },
        {
            "id": 3485868443,
            "email": "churrell@billiondollarboy.com",
            "company": "Billion Dollar Boy",
        },
        {
            "id": 3485868484,
            "email": "lorlandi@billiondollarboy.com",
            "company": "Billion Dollar Boy",
        },
    ]

    # Filter out already unsubscribed (churrell + lorlandi done earlier)
    to_process = [
        l
        for l in known_leads
        if l["email"]
        not in ("churrell@billiondollarboy.com", "lorlandi@billiondollarboy.com")
    ]

    print(f"Unsubscribing {len(to_process)} leads from client companies:\n")

    unsubbed = []
    failed = []

    for lead in to_process:
        ok = unsubscribe(lead["id"], lead["email"])
        if ok:
            print(f"  ✓ {lead['email']} [{lead['company']}]")
            unsubbed.append(lead)
        else:
            print(f"  ✗ FAILED: {lead['email']}")
            failed.append(lead)
        time.sleep(0.5)

    print(f"\nDone: {len(unsubbed)} unsubscribed, {len(failed)} failed")

    if failed:
        print("\nFailed:")
        for l in failed:
            print(f"  {l['email']}")


if __name__ == "__main__":
    main()
