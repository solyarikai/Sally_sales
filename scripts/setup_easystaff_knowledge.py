#!/usr/bin/env python3
"""
Populate EasyStaff RU (project 40) with knowledge and reply template.

Based on analysis of 46 qualified lead conversations from SmartLead.
Extracts operator reply patterns, EasyStaff value proposition, and ICP insights.

Usage: python scripts/setup_easystaff_knowledge.py [--api-url URL]
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

DEFAULT_API_URL = "http://localhost:8000/api"
HEADERS = {"Content-Type": "application/json", "X-Company-ID": "1"}
PROJECT_ID = 40

# ─── EasyStaff Reply Template ───────────────────────────────────────────
# Built from analysis of 46+ real operator conversations

EASYSTAFF_REPLY_TEMPLATE = """You are replying as {sender_name}{sender_position_line}{sender_company_line} — a sales partner at EasyStaff.io.

EasyStaff is a global freelancer payment platform. Key value proposition:
- Payments to contractors in 180+ countries (CIS, Europe, Asia, LatAm)
- Payment methods: bank transfer, crypto (USDT), local currency
- Flexible tariffs: percentage (3-5%) OR fixed ($39/task), no hidden fees
- 0% currency conversion fee
- One contract instead of dozens with individual contractors
- Full closing documents and invoicing handled by EasyStaff
- VAT only on commission (not on the full payment amount)
- Free withdrawal for freelancers
- Bulk payments via Excel upload

CONTEXT about this lead:
Subject: {subject}
Lead reply: {body}
Category: {category}
Lead: {first_name} {last_name}
Company: {company}

REPLY RULES (based on real operator patterns — follow these strictly):

1. LANGUAGE: Always reply in Russian. Match the lead's tone (formal/informal).

2. FOR "interested" leads asking for a presentation:
   - Short greeting with their name
   - "Спасибо за интерес/ответ!" or similar brief thanks
   - "Прикрепил презентацию." (always say this — operator attaches PDF separately)
   - If the lead seems engaged, add key advantages:
     • Один договор с нами вместо десятков с исполнителями
     • Гибкие тарифы (% или фикс), без скрытых платежей
     • 0% за конвертацию валют
   - Sign off: sender name + "Partner @ easystaff.io" + "Telegram: @sokolovvdan"

3. FOR "interested" leads with questions or specific needs:
   - Address their specific question/concern directly
   - Provide relevant EasyStaff capability info
   - Suggest a 15-minute call to discuss in detail
   - Offer time slots (business hours CET)

4. FOR "meeting_request" leads:
   - Brief enthusiastic confirmation
   - "Предлагаю созвониться на 15 минут — покажем, как это работает на практике"
   - Ask for preferred time/timezone
   - If they give Telegram/phone, acknowledge and say colleague will reach out

5. FOR leads mentioning ICE Barcelona or conferences:
   - Keep the conference reference natural
   - Don't fabricate conversations that didn't happen
   - If lead corrects a mixup, acknowledge gracefully with humor

6. FOR leads who are already customers or using competitors:
   - Don't push aggressively
   - Offer comparison or savings calculation
   - "Можем рассчитать экономию на вашем примере"

7. FOR "not_interested" leads (OBJECTION HANDLING):
   a) Flat rejection ("не актуально", "не интересует", "нет"):
      - Keep it SHORT (2-3 sentences max)
      - Thank them for the response
      - Leave the door open: "Если в будущем появится интерес — буду рад помочь"
      - Do NOT pitch or list advantages — they said no
   b) Small volume ("маленькие объемы", "всего 2 человека"):
      - Acknowledge their situation empathetically
      - Mention that EasyStaff works with any volume, even 1-2 contractors
      - Highlight the fixed $39/task option for small volumes
      - "Можем начать с малого, без минимального объёма"
   c) Already using another solution ("используем другое", "уже клиент"):
      - Thank them and don't push
      - Briefly offer a savings comparison if appropriate
      - "Если захотите сравнить условия — всегда открыты"
   d) Rude/aggressive ("отстань", "перестань писать"):
      - Short, professional, graceful exit
      - "Приношу извинения за беспокойство. Удалю ваш контакт из рассылки."
      - Do NOT engage further or argue

8. FOR "question" leads:
   a) Pricing questions ("цены", "тарифы", "условия"):
      - Give specific numbers: 3-5% or $39/task fixed
      - Mention 0% conversion fee
      - Offer to send detailed presentation or schedule a call
   b) Legal/compliance questions ("юрлицо", "документы", "резидент"):
      - EasyStaff is a legal entity providing full closing documents
      - One contract covers all contractors
      - Invoicing and reporting handled by EasyStaff
   c) Capability questions ("работаете с...", "можете..."):
      - Answer directly based on EasyStaff capabilities
      - 180+ countries, CIS focus, bank/crypto/local payments
      - If unclear, suggest a call for detailed discussion
   d) Request for presentation with pricing:
      - "Прикрепил презентацию с тарифами."
      - Briefly list key highlights relevant to their question

9. FOR "wrong_person" leads (referrals):
   - Thank them for letting you know
   - Ask politely for the right contact: "Не подскажете, кто в вашей компании отвечает за расчёты с подрядчиками?"
   - Keep it one sentence, don't over-explain

10. NEVER:
   - Use placeholder brackets like [Your Name], [Ваше имя]
   - Promise to send a presentation without being asked (let the operator handle attachments)
   - Invent details about the lead's company not present in the data
   - Sign as "CFO" or use the lead's info in the signature
   - Respond in English unless the lead wrote in English
   - Send long pitches to people who said "no" — respect their decision

Respond with ONLY a JSON object:
{{"subject": "Re: {subject}", "body": "<reply text>", "tone": "<professional|friendly|formal>"}}"""


# ─── Project Knowledge Entries ──────────────────────────────────────────

KNOWLEDGE_ENTRIES = [
    # ICP
    ("icp", "target_market", "Russian-speaking companies with HQ in Russia, CIS, Europe, UAE working with international freelancers/contractors"),
    ("icp", "target_roles", "CFO, CEO, COO, Head of Finance, HR Director — decision makers for payment operations"),
    ("icp", "target_industries", "IT/SaaS, FinTech, iGaming, Crypto, E-commerce, Consulting — companies with distributed teams"),
    ("icp", "positive_signals", "Works with freelancers abroad, has payment difficulties in CIS, uses competitors like Deel/Payoneer, mentioned specific needs at conferences"),
    ("icp", "negative_signals", "Only domestic operations, no freelancers, already satisfied with current solution, very small team (<5 people)"),
    ("icp", "qualification_criteria", "Has international contractors, monthly payment volume >$5K, open to discussing alternatives"),

    # Outreach
    ("outreach", "email_sequence", "1) Cold email about freelancer payment difficulties 2) Follow-up about hidden fees/taxes 3) Check if emails arrive 4) Offer presentation 5) Last chance with competitor comparison"),
    ("outreach", "value_prop_short", "EasyStaff.io помогает 200+ компаниям платить подрядчикам в 180+ странах, включая СНГ, с гибкой комиссией (фикс или процент)"),
    ("outreach", "sender_identity", "Danila Sokolov, Partner @ easystaff.io, Telegram: @sokolovvdan"),
    ("outreach", "ice_campaign_context", "ICE Barcelona conference campaign — personalized follow-ups referencing the event, mentioning companies and conversations from the conference"),

    # Contacts
    ("contacts", "operator_team", "Danila Sokolov (Partner, main sender), Alex P. (alex.p@easystaff.io, calls & demos), Eleonora (Telegram: @eleeaon, demos), Катя (LinkedIn DMs)"),
    ("contacts", "reply_channels", "Email via SmartLead, LinkedIn via GetSales (9 sender profiles), Telegram for warm leads"),

    # GTM
    ("gtm", "campaign_naming", "EasyStaff - Russian DM [geo/segment], EasyStaff - HQ in Russia, EasyStaff RU - [sender name]"),
    ("gtm", "pricing", "Percentage: 3-5% depending on monthly volume. Fixed: $39/task. No conversion fees. Free withdrawal for freelancers."),
    ("gtm", "competitors", "Deel, Payoneer, Mellow (subsidiary for specific cases), local banks"),
    ("gtm", "objection_handling", "Already have solution → offer savings comparison. Too expensive → explain transparent pricing vs hidden fees. Not relevant → suggest presentation for future reference. Small volumes → $39/task fixed, no minimum. Rude rejection → apologize and unsubscribe gracefully. Wrong person → ask for referral to finance/payments team."),

    # Notes
    ("notes", "operator_reply_style", "Short, professional, friendly. Always in Russian. Attaches presentation when asked. Mentions key advantages for engaged leads. Signs off as 'Danila Sokolov, Partner @ easystaff.io'. Follow-up after 3-5 days."),
    ("notes", "follow_up_pattern", "After sending presentation: 'Подскажите, пожалуйста, было время изучить наше предложение?' after 3-5 days"),

    # Files (for quick operator download in reply queue)
    # Set the actual URL via API: PUT /api/projects/40/knowledge/files/presentation
    # ("files", "presentation", "https://drive.google.com/file/d/YOUR_FILE_ID/view"),
]


def api_request(url, method="GET", data=None):
    """Make HTTP API request."""
    req = urllib.request.Request(url, headers=HEADERS, method=method)
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {body[:200]}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Setup EasyStaff RU knowledge")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API base URL")
    args = parser.parse_args()
    base = args.api_url.rstrip("/")

    print("=" * 60)
    print("  EasyStaff RU Knowledge Setup")
    print("=" * 60)

    # Step 1: Update project sender info
    print("\n1. Setting sender info on project 40...")
    try:
        result = api_request(
            f"{base}/contacts/projects/{PROJECT_ID}",
            method="PATCH",
            data={
                "sender_name": "Danila Sokolov",
                "sender_position": "Partner",
                "sender_company": "easystaff.io",
            },
        )
        print(f"   OK: sender_name={result.get('sender_name')}")
    except Exception as e:
        print(f"   WARN: {e}")

    # Step 2: Create reply prompt template
    print("\n2. Creating reply prompt template...")
    try:
        result = api_request(
            f"{base}/replies/prompt-templates",
            method="POST",
            data={
                "name": "EasyStaff RU - Knowledge-Powered",
                "prompt_type": "reply",
                "prompt_text": EASYSTAFF_REPLY_TEMPLATE,
                "is_default": False,
            },
        )
        template_id = result["id"]
        print(f"   OK: template_id={template_id}")
    except Exception as e:
        print(f"   WARN: {e}")
        template_id = None

    # Step 3: Assign template to project
    if template_id:
        print(f"\n3. Assigning template {template_id} to project 40...")
        try:
            result = api_request(
                f"{base}/contacts/projects/{PROJECT_ID}",
                method="PATCH",
                data={"reply_prompt_template_id": template_id},
            )
            print(f"   OK: reply_prompt_template_id={result.get('reply_prompt_template_id')}")
        except Exception as e:
            print(f"   WARN: {e}")

    # Step 4: Populate project knowledge
    print(f"\n4. Populating {len(KNOWLEDGE_ENTRIES)} knowledge entries...")
    for category, key, value in KNOWLEDGE_ENTRIES:
        try:
            api_request(
                f"{base}/projects/{PROJECT_ID}/knowledge/{category}/{key}",
                method="PUT",
                data={"value": value, "source": "manual"},
            )
            print(f"   OK: [{category}] {key}")
        except Exception as e:
            print(f"   WARN [{category}] {key}: {e}")

    # Step 5: Regenerate drafts for target leads
    print("\n5. Regenerating drafts for target leads...")
    target_reply_ids = [34894, 34861]  # md@activa-mgm.lv, cfo@vintogroup.com
    for reply_id in target_reply_ids:
        try:
            result = api_request(
                f"{base}/replies/{reply_id}/regenerate-draft",
                method="POST",
            )
            print(f"   Reply {reply_id}:")
            print(f"     Category: {result.get('category')}")
            print(f"     Draft: {result.get('draft_reply', '')[:200]}")
            print()
        except Exception as e:
            print(f"   WARN reply {reply_id}: {e}")

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
