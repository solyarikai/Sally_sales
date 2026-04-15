#!/usr/bin/env python3
"""
Find all OnSocial paid client contacts in SmartLead and unsubscribe them.
"""

import requests
import time

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"

EMAILS = [
    "adam@hashtagpaid.com",
    "aditya.jami@meltwater.com",
    "aholt@disruptiveadvertising.com",
    "aja.smith@wearesocial.com",
    "alexa@digitalvoices.com",
    "alexandra.romet@wearesocial.com",
    "alex@openinfluence.com",
    "alex@theinfluenceroom.com",
    "ali.spillane@wearesocial.com",
    "amir@zoomph.com",
    "amy.watts@wearesocial.com",
    "andrew.tolhurst@meltwater.com",
    "anthony@openinfluence.com",
    "apowell@billiondollarboy.com",
    "ariske@hashtagpaid.com",
    "atef@boostiny.com",
    "austeja.baciunaite@billo.app",
    "beatrice.infrano@wearesocial.com",
    "bgold@hashtagpaid.com",
    "bradley.zucker@izea.com",
    "bryan.bartley@vidiq.com",
    "bryan@moburst.com",
    "camilla.beghi@wearesocial.com",
    "chafia.benosmane@wearesocial.com",
    "chandni@digitalvoices.com",
    "chen@moburst.com",
    "chris.hackney@meltwater.com",
    "chris.jacks@later.com",
    "christopher.naufel@wearesocial.com",
    "churrell@billiondollarboy.com",
    "courtney.calderon@moburst.com",
    "cris.forlani@wearesocial.com",
    "dana.byrnes@wearesocial.com",
    "daniel.schotland@linqia.com",
    "david.hansson@gigapay.co",
    "denicia.lew@wearesocial.com",
    "donatas@billo.app",
    "dragutin@smartocto.com",
    "dyah.ramadhani@wearesocial.com",
    "ed@billiondollarboy.com",
    "eimear@brandbassador.com",
    "elena.stoyanova@reachbird.io",
    "elise.bola@digitalvoices.com",
    "emer.mcdevitt@wearesocial.com",
    "emily@theinfluenceroom.com",
    "emin@keepface.com",
    "emma.ilaria@wearesocial.com",
    "emma@moburst.com",
    "francesca@theinfluenceroom.com",
    "georgia.goodwin@digitalvoices.com",
    "gilad@moburst.com",
    "grace@fohr.co",
    "gustav@gigapay.co",
    "hagai@moburst.com",
    "hayden.carter@vidiq.com",
    "hjalmar@gigapay.co",
    "hshumway@disruptiveadvertising.com",
    "huixuan.teo@wearesocial.com",
    "ieva.m@billo.app",
    "igor.schtein@vidiq.com",
    "irit@moburst.com",
    "ivan.torres@wearesocial.com",
    "jace@disruptiveadvertising.com",
    "james@billiondollarboy.com",
    "james@fohr.co",
    "jaoui.liu@wearesocial.com",
    "javed@lottiefiles.com",
    "jbrazier@billiondollarboy.com",
    "jenny@digitalvoices.com",
    "jgause@disruptiveadvertising.com",
    "joey@openinfluence.com",
    "john.box@meltwater.com",
    "john@zoomph.com",
    "jorn.lyseggen@meltwater.com",
    "joshm@zoomph.com",
    "jtrott@hashtagpaid.com",
    "justin.withers@later.com",
    "justin.x.foley@later.com",
    "kali@hashtagpaid.com",
    "kate.hicks@wearesocial.com",
    "katie.lockwood@wearesocial.com",
    "katie@moburst.com",
    "kayci.webster@izea.com",
    "k@lottiefiles.com",
    "kmorrow@billiondollarboy.com",
    "krithika.raj@meltwater.com",
    "kwest@hashtagpaid.com",
    "kyle.hartsook@sideqik.com",
    "lauren.coleman@wearesocial.com",
    "lauren.marlow@wearesocial.com",
    "leaton@billiondollarboy.com",
    "lindsay.gardner@izea.com",
    "lior@moburst.com",
    "liz.svilanejones@wearesocial.com",
    "lorlandi@billiondollarboy.com",
    "maggie@moburst.com",
    "marco@openinfluence.com",
    "margot.riff@wearesocial.com",
    "maria.bersteneva@brandwatch.com",
    "maria.kolesnichenko@vidiq.com",
    "maria.sipka@linqia.com",
    "mario@gigapay.co",
    "mark@theinfluenceroom.com",
    "matt@brandbassador.com",
    "matthew.stimson@wearesocial.com",
    "melanie@digitalvoices.com",
    "michael.harris@moburst.com",
    "mike@moburst.com",
    "molly.mcaleavey@wearesocial.com",
    "mubashir@brandbassador.com",
    "muhammed.karabacak@reachbird.io",
    "murray@webfluential.com",
    "mwebber@billiondollarboy.com",
    "nader_alizadeh@linqia.com",
    "nader@linqia.com",
    "nathalie.albertus@wearesocial.com",
    "nathalie.hite@wearesocial.com",
    "nattu@lottiefiles.com",
    "nick@zoomph.com",
    "nikki@linqia.com",
    "nour.douzdar@wearesocial.com",
    "ntrewinmarshall@billiondollarboy.com",
    "ocripps@billiondollarboy.com",
    "ole@brandbassador.com",
    "ottavio.nava@wearesocial.com",
    "patrick@disruptiveadvertising.com",
    "patrick.venetucci@izea.com",
    "peter.li@vidiq.com",
    "philipp@reachbird.io",
    "phoebe.law@wearesocial.com",
    "psouthey@billiondollarboy.com",
    "raiha@gigapay.co",
    "reed.king@wearesocial.com",
    "rsandie@vidiq.com",
    "rs@wearesocial.com",
    "sabrina.varaldo@wearesocial.com",
    "sarah.boak@wearesocial.com",
    "sasha.fraser@digitalvoices.com",
    "saurabh.singh@linqia.com",
    "scott.gibbs@meltwater.com",
    "scott@later.com",
    "sean@zoomph.com",
    "sebastian.niemann@eqolot.com",
    "selstob@brandwatch.com",
    "shreyas.sukumar@wearesocial.com",
    "silvestro.barca@wearesocial.com",
    "suzie.shaw@wearesocial.com",
    "tabi@heepsy.com",
    "tadas@billo.app",
    "tahi@brandbassador.com",
    "tanya@theinfluenceroom.com",
    "ted.farrell@linqia.com",
    "thomasadams@brandbassador.com",
    "thomas@brandbassador.com",
    "thomas@gigapay.co",
    "thomas@zoomph.com",
    "tony.hui@vidiq.com",
    "trent@digitalvoices.com",
    "vagif@keepface.com",
]


def fetch_lead(email: str):
    r = requests.get(
        f"{BASE}/leads",
        params={"api_key": API_KEY, "email": email},
        timeout=15,
    )
    if r.status_code == 200:
        data = r.json()
        if data and isinstance(data, dict) and data.get("id"):
            return data
    return None


def unsubscribe(lead_id: int) -> bool:
    r = requests.post(
        f"{BASE}/leads/unsubscribe",
        params={"api_key": API_KEY},
        json={"lead_id": lead_id},
        timeout=15,
    )
    return r.status_code == 200


def main():
    print(f"Processing {len(EMAILS)} emails...\n")

    found = []
    not_found = []
    unsubbed = []
    already = []
    failed = []

    for i, email in enumerate(EMAILS, 1):
        lead = fetch_lead(email)
        if not lead:
            not_found.append(email)
            print(f"  [{i}/{len(EMAILS)}] NOT FOUND: {email}")
            time.sleep(0.3)
            continue

        if lead.get("is_unsubscribed"):
            already.append(email)
            print(f"  [{i}/{len(EMAILS)}] ALREADY UNSUB: {email}")
            time.sleep(0.3)
            continue

        found.append(email)
        lead_id = int(lead["id"])
        campaigns = [c["campaign_name"] for c in lead.get("lead_campaign_data", [])]
        ok = unsubscribe(lead_id)
        if ok:
            unsubbed.append(email)
            print(
                f"  [{i}/{len(EMAILS)}] ✓ UNSUBSCRIBED: {email} | campaigns: {', '.join(campaigns)}"
            )
        else:
            failed.append(email)
            print(f"  [{i}/{len(EMAILS)}] ✗ FAILED: {email}")
        time.sleep(0.5)

    print(f"\n{'=' * 60}")
    print(f"Total processed : {len(EMAILS)}")
    print(f"Found in SL     : {len(found) + len(already)}")
    print(f"Not in SL       : {len(not_found)}")
    print(f"Already unsub   : {len(already)}")
    print(f"Unsubscribed now: {len(unsubbed)}")
    print(f"Failed          : {len(failed)}")

    if failed:
        print("\nFailed emails:")
        for e in failed:
            print(f"  {e}")


if __name__ == "__main__":
    main()
