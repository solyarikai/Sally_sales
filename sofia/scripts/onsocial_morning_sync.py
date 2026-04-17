#!/usr/bin/env python3
"""
OnSocial Morning Sync — runs OOO, Wrong Person, Pause Booked.
Sends ONE combined Telegram report.

Cron:
  0 6 * * 1-5 cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/onsocial_morning_sync.py >> /tmp/onsocial_morning_sync.log 2>&1
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone

CHAT_ID = os.environ.get("SOFIA_TG_CHAT_ID", "7380803777")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SMARTLEAD_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WRONG_PERSON_CAMPAIGN_ID = 3092917


def fetch_referral_template():
    """Fetch Step 1 subject+body from the WRONG-PERSON-referral campaign."""
    if not SMARTLEAD_KEY:
        return None
    try:
        import httpx
        r = httpx.get(
            f"https://server.smartlead.ai/api/v1/campaigns/{WRONG_PERSON_CAMPAIGN_ID}/sequences",
            params={"api_key": SMARTLEAD_KEY},
            timeout=15,
        )
        r.raise_for_status()
        steps = r.json()
        if not steps:
            return None
        step1 = steps[0]
        variants = step1.get("seq_variants") or [{}]
        v = variants[0]
        return {
            "subject": v.get("subject") or step1.get("subject", ""),
            "body": v.get("email_body") or step1.get("email_body", ""),
        }
    except Exception as e:
        print(f"Failed to fetch referral template: {e}")
        return None


def html_to_text(html):
    """Simple HTML to text for TG display."""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_email(template, first_name, company_name):
    """Legacy: render with first_name == colleague_name (broken old behavior)."""
    return render_email_v2(template, first_name, first_name, company_name)


def render_email_v2(template, first_name, colleague_name, company_name):
    """Render referral template with distinct first_name (new contact) vs colleague_name (referrer)."""
    if not template:
        return None
    subject = template["subject"]
    body = html_to_text(template["body"])
    for placeholder, value in [
        ("{{first_name}}", first_name or ""),
        ("{{colleague_name}}", colleague_name or first_name or ""),
        ("{{company_name}}", company_name or ""),
    ]:
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)
    return subject, body


def run_script(cmd, label):
    """Run a script, return (stdout, success)."""
    print(f"\n{'='*40}\n{label}\n{'='*40}")
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, cwd=REPO,
        )
        output = r.stdout + r.stderr
        print(output)
        return output, r.returncode == 0
    except subprocess.TimeoutExpired:
        msg = f"{label}: TIMEOUT (600s)"
        print(msg)
        return msg, False
    except Exception as e:
        msg = f"{label}: ERROR {e}"
        print(msg)
        return msg, False


def parse_ooo(output):
    """Extract key metrics from OOO sync output."""
    lines = []

    m = re.search(r"(\d+) OOO, (\d+) uploaded, (\d+) waiting", output)
    if m:
        total, uploaded, waiting = m.group(1), m.group(2), m.group(3)
        lines.append(f"  {total} OOO total, +{uploaded} re-engaged, {waiting} waiting")
    else:
        lines.append("  No data")

    m = re.search(r"(\d+) repeat re-parsed", output)
    if m and int(m.group(1)) > 0:
        lines.append(f"  {m.group(1)} repeat OOO re-parsed")

    # Capture uploaded lead names
    names = re.findall(r"^\s+\[?REPEAT\]?(.+@.+)\s+\(.+?\)\s+-\s+.+$", output, re.MULTILINE)
    for n in names[:5]:
        lines.append(f"  - {n.strip()}")

    # API response
    m = re.search(r"upload_count=(\d+), already_added=(\d+)", output)
    if m and int(m.group(2)) > 0:
        lines.append(f"  ⚠️ already_added={m.group(2)} (dedup)")

    return "\n".join(lines)


def parse_wrong_person(output, template):
    """Extract leads from Wrong Person stdout and render email previews."""
    # Parse lead lines: "email | first_name | company | from: campaign (referred by X)"
    # (logger prefix may precede: "2026-... - INFO -   email@... | ...")
    leads = []
    seen = set()
    for line in output.splitlines():
        m = re.search(r"(\S+@\S+\.\S+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*from:\s*(.+?)$", line)
        if m:
            email = m.group(1).strip()
            if email in seen:
                continue
            seen.add(email)
            tail = m.group(4).strip()
            ref_m = re.search(r"\(referred by ([^)]+)\)\s*$", tail)
            colleague = ref_m.group(1).strip() if ref_m else ""
            campaign = tail[: ref_m.start()].strip() if ref_m else tail
            leads.append({
                "email": email,
                "first_name": m.group(2).strip(),
                "company": m.group(3).strip(),
                "campaign": campaign,
                "colleague_name": colleague,
            })

    # Parse result stats
    added = 0
    failed = 0
    m = re.search(r"Result:\s*added=(\d+),\s*failed=(\d+)", output)
    if m:
        added = int(m.group(1))
        failed = int(m.group(2))

    if not leads and added == 0:
        return "  No new replies", []

    result_lines = [f"  +{added} synced, {failed} failed" if added or failed else f"  {len(leads)} found"]

    # Render email preview for each lead
    email_previews = []
    for lead in leads[:5]:
        ref_suffix = f" ← referred by {lead['colleague_name']}" if lead.get("colleague_name") else ""
        result_lines.append(f"  - {lead['first_name']} <{lead['email']}> ({lead['company']}){ref_suffix}")
        if template:
            colleague = lead.get("colleague_name") or lead["first_name"]
            rendered = render_email_v2(template, lead["first_name"], colleague, lead["company"])
            if rendered:
                subj, body = rendered
                email_previews.append({
                    "lead": f"{lead['first_name']} <{lead['email']}>",
                    "subject": subj,
                    "body": body,
                })

    if len(leads) > 5:
        result_lines.append(f"  ... and {len(leads) - 5} more")

    return "\n".join(result_lines), email_previews


def parse_pause(output):
    """Extract key metrics from Pause Booked."""
    paused = "0"
    checked = "0"

    m = re.search(r"Leads paused:\s*(\d+)", output)
    if m:
        paused = m.group(1)

    m = re.search(r"Leads checked:\s*(\d+)", output)
    if m:
        checked = m.group(1)

    result = f"  Checked: {checked}, paused: {paused}"

    if int(paused) > 0:
        names = re.findall(r"Pausing:\s*(.+?)(?:\s*-\s*|$)", output)
        for n in names[:5]:
            result += f"\n  - {n.strip()}"

    return result


def send_tg(text):
    """Send Telegram message, splitting at 4000 chars if needed."""
    if not TG_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set, skipping TG")
        return
    try:
        import httpx
        # Split into chunks of ~4000 chars, breaking on email preview boundaries
        chunks = []
        if len(text) <= 4000:
            chunks = [text]
        else:
            # Split at "📧 Email" markers
            parts = re.split(r"(\n\n📧 Email)", text)
            current = parts[0]
            i = 1
            while i < len(parts):
                # parts[i] is the separator "\n\n📧 Email", parts[i+1] is the content after
                piece = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
                if len(current) + len(piece) > 4000:
                    chunks.append(current)
                    current = piece.lstrip("\n")
                else:
                    current += piece
                i += 2
            if current:
                chunks.append(current)

        for idx, chunk in enumerate(chunks):
            r = httpx.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": chunk},
                timeout=15,
            )
            print(f"Telegram sent [{idx+1}/{len(chunks)}]: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")


def main():
    now = datetime.now(timezone.utc)
    print(f"[{now.strftime('%Y-%m-%d %H:%M')} UTC] OnSocial Morning Sync")

    py = sys.executable

    # Fetch referral email template once
    referral_template = fetch_referral_template()

    # 1. OOO Sync
    ooo_out, ooo_ok = run_script(
        [py, "sofia/scripts/smartlead_ooo_sync_universal.py", "--project", "OnSocial", "--no-tg"],
        "OOO Re-engagement Sync",
    )

    # 2. Wrong Person Sync (no --chat-id = no individual TG)
    wp_out, wp_ok = run_script(
        [py, "sofia/scripts/sync_wrong_person.py", "--project", "OnSocial", "--campaign-id", str(WRONG_PERSON_CAMPAIGN_ID)],
        "Wrong Person Sync",
    )

    # 3. Pause Booked
    pause_out, pause_ok = run_script(
        [py, "sofia/scripts/smartlead_pause_booked_leads.py", "--execute", "--no-tg"],
        "Auto-Pause Booked/Qualified",
    )

    wp_summary, email_previews = parse_wrong_person(wp_out, referral_template)

    # Build combined message
    ooo_icon = "✅" if "uploaded" in ooo_out and not re.search(r"\b0 uploaded", ooo_out) else "📭"
    wp_icon = "✅" if email_previews else "🔄"
    pause_icon = "🚫" if not re.search(r"Leads paused:\s*0", pause_out) else "⏸️"

    msg = f"📊 OnSocial Morning Sync — {now.strftime('%d.%m.%Y')}\n"
    msg += f"\n{ooo_icon} OOO Re-engagement\n{parse_ooo(ooo_out)}\n"
    msg += f"\n{wp_icon} Wrong Person → Referral\n{wp_summary}\n"
    msg += f"\n{pause_icon} Auto-Pause (Booked/Qualified)\n{parse_pause(pause_out)}"

    # Append email previews for each Wrong Person lead
    for i, preview in enumerate(email_previews, 1):
        msg += f"\n\n📧 Email #{i} → {preview['lead']}\n"
        msg += f"Subject: {preview['subject']}\n\n"
        msg += preview['body']

    # Add errors if any
    errors = []
    if not ooo_ok:
        errors.append("OOO sync")
    if not wp_ok:
        errors.append("Wrong Person")
    if not pause_ok:
        errors.append("Pause Booked")
    if errors:
        msg += f"\n\n⚠️ Errors in: {', '.join(errors)}"

    print(f"\n{'='*40}\nCOMBINED REPORT\n{'='*40}")
    print(msg)

    send_tg(msg)
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M')} UTC] Done.")


if __name__ == "__main__":
    main()
