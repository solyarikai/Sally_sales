#!/usr/bin/env python3.11
"""Filter pipeline output CSVs against kb_blocklist from DB."""

import csv
from pathlib import Path

# Blocklist: domains and specific emails from DB
BLOCKLIST_DOMAINS = {
    "billiondollarboy.com",
    "talkshop.live",
    "commentsold.com",
    "smartzer.com",
    "videoshops.com",
    "firework.tv",
    "droppii.com",
    "walee.ae",
    "catenoid.net",
    "sugarreach.com",
    "likeminds.community",
    "fanbridge.app",
    "sankmo.in",
    "thepeoplesinc.org",
    "mandu.com.vn",
    "10xcrew.com",
    "afrovivo-waitlist.vercel.app",
    "alive.app.br",
    "ammi.cc",
    "apptile.com",
    "basketstudios.com",
    "borderxmedia.com",
    "butterflyagency.io",
    "buzzspark.io",
    "caast.tv",
    "cataloghub.in",
    "clicktivated.com",
    "connnecta.com.br",
    "creatorsclub.com",
    "creatorsclub.world",
    "dangdi.eu",
    "ellicreators.com",
    "euka.ai",
    "frnt.co",
    "glamourbae.com",
    "goodpix.co",
    "kerv.ai",
    "limelighthq.com",
    "linkable.link",
    "linkfluencer.io",
    "live2.ai",
    "livesel.com",
    "madeinlive.fr",
    "makeitshoppable.com",
    "mimo.com.br",
    "newmcn.com",
    "nws.ai",
    "ouishopp.com",
    "paragonsocialcommerce.com",
    "raqk.co",
    "reelup.io",
    "sailawaymedia.com",
    "seeen.com",
    "shoparonline.com",
    "shopclips.app",
    "shopreel.ai",
    "shopsense.ai",
    "silvr.ai",
    "simpleinfluence.co.za",
    "smartcommerce.com",
    "spree.city",
    "starlive.tech",
    "streamagency.com",
    "streamerce.live",
    "streamshop.com.br",
    "swipeup.app",
    "theartofliveselling.com",
    "thecreativeagencyboston.com",
    "topdrwr.io",
    "trendio.ai",
    "trendtribecreators.com",
    "trulyfree.com",
    "veels.pro",
    "veyra.co.in",
    "videopoint.ai",
    "vidvi.com",
    "weedeo.co",
    "widde.io",
    "yourshoppingstream.com",
    "zaply.io",
    "zellor.com",
}

BLOCKLIST_EMAILS = {
    "shawkins@talkshop.live",
    "bryan@talkshop.live",
    "ivan@talkshop.live",
    "andrea@talkshop.live",
    "gautam.goswami@commentsold.com",
    "jwong@commentsold.com",
    "karoline@smartzer.com",
    "cory@videoshops.com",
    "matth@videoshops.com",
    "yifan@fireworkhq.com",
    "matt@fireworkhq.com",
    "son.nguyen@droppii.com",
    "nhat.nguyen@droppii.com",
    "ahsan.tahir@walee.pk",
    "kse@catenoid.net",
    "mk.kim@catenoid.net",
    "dimitar@sugarreach.com",
    "melissa@sugarreach.com",
    "roberto@sugarreach.com",
    "natesh@likeminds.io",
    "nipun.goyal@likeminds.io",
    "kay@shinest.co.kr",
    "nikhil@sankmo.com",
    "chirag@sankmo.com",
    "sabrina@seraphinaai.com",
    "jerry@mandu.com.vn",
    "quan@mandu.com.vn",
}


def get_domain(email_or_website: str) -> str:
    s = email_or_website.strip().lower()
    if not s:
        return ""
    if "@" in s:
        return s.split("@")[-1]
    s = s.replace("https://", "").replace("http://", "").split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def is_blocked(row: dict) -> tuple[bool, str]:
    email = row.get("email", "").strip().lower()
    website = row.get("website", "").strip().lower()

    if email and email in BLOCKLIST_EMAILS:
        return True, f"email:{email}"

    email_domain = get_domain(email) if email else ""
    if email_domain and email_domain in BLOCKLIST_DOMAINS:
        return True, f"domain:{email_domain}"

    web_domain = get_domain(website) if website else ""
    if web_domain and web_domain in BLOCKLIST_DOMAINS:
        return True, f"website:{web_domain}"

    return False, ""


OUTPUT_DIR = Path(__file__).parent.parent / "output" / "Project_42" / "pipeline"

segments = ["IMAGENCY", "INFPLAT", "SOCCOM"]
date = "2026-04-10"

total_in = total_out = total_blocked = 0

for seg in segments:
    for kind in ["leads_with_email", "leads_linkedin_only"]:
        fname = f"{kind}_{seg}_{date}.csv"
        fpath = OUTPUT_DIR / fname
        if not fpath.exists():
            print(f"  ⚠ Not found: {fname}")
            continue

        with open(fpath) as f:
            rows = list(csv.DictReader(f))

        kept = []
        blocked = []
        for row in rows:
            block, reason = is_blocked(row)
            if block:
                blocked.append((row, reason))
            else:
                kept.append(row)

        total_in += len(rows)
        total_out += len(kept)
        total_blocked += len(blocked)

        if blocked:
            print(
                f"\n  {seg} / {kind}: {len(rows)} → {len(kept)} (убрано {len(blocked)})"
            )
            for row, reason in blocked:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                print(f"    ✗ {name} [{reason}]")
        else:
            print(f"  {seg} / {kind}: {len(rows)} → {len(kept)} (чисто)")

        # Overwrite file
        if blocked:
            with open(fpath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(kept)

print(f"\n{'=' * 50}")
print(f"Итого: {total_in} → {total_out} (убрано {total_blocked})")
