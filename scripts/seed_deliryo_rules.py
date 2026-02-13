"""Seed 3 default Deliryo push rules."""
import asyncio
import httpx
import os
import json
from app.db.database import async_session_maker
from app.models.pipeline import CampaignPushRule
from sqlalchemy import select


# Russian sequences with {{first_name}}
RU_SEQUENCES_WITH_NAME = [
    {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "Партнёрство: конвертация для ваших клиентов",
        "email_body": "<p>{{first_name}}, добрый день!</p><p>Мы — Deliryo, платформа для конвертации RUB ↔ USDT для состоятельных клиентов.</p><p>Если среди ваших клиентов есть те, кому нужна конвертация рублей — мы можем стать вашим технологическим партнёром.</p><p>Готовы обсудить условия?</p>"
    },
    {
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "Re: Партнёрство: конвертация для ваших клиентов",
        "email_body": "<p>{{first_name}}, хотел уточнить — получили ли вы моё предыдущее письмо?</p><p>Мы работаем с family offices, wealth managers и инвестиционными компаниями, предоставляя быструю конвертацию RUB ↔ USDT с выгодным курсом.</p><p>Буду рад коротко пообщаться.</p>"
    },
    {
        "seq_number": 3,
        "seq_delay_details": {"delay_in_days": 5},
        "subject": "Re: Re: Партнёрство: конвертация для ваших клиентов",
        "email_body": "<p>{{first_name}}, пишу в последний раз — если тема неактуальна, просто дайте знать.</p><p>Если же у ваших клиентов есть потребность в конвертации рублей, давайте обсудим — возможно, это будет полезно для обеих сторон.</p>"
    },
]

# Russian sequences WITHOUT {{first_name}} (for info@, contact@ etc.)
RU_SEQUENCES_NO_NAME = [
    {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "Партнёрство: конвертация RUB ↔ USDT",
        "email_body": "<p>Добрый день!</p><p>Мы — Deliryo, платформа для конвертации RUB ↔ USDT для состоятельных клиентов.</p><p>Если среди ваших клиентов есть те, кому нужна конвертация рублей — мы можем стать вашим технологическим партнёром.</p><p>Готовы обсудить условия?</p>"
    },
    {
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "Re: Партнёрство: конвертация RUB ↔ USDT",
        "email_body": "<p>Добрый день, хотел уточнить — получили ли вы предыдущее письмо?</p><p>Мы работаем с family offices, wealth managers и инвестиционными компаниями, предоставляя быструю конвертацию RUB ↔ USDT с выгодным курсом.</p><p>Буду рад коротко пообщаться.</p>"
    },
    {
        "seq_number": 3,
        "seq_delay_details": {"delay_in_days": 5},
        "subject": "Re: Re: Партнёрство: конвертация RUB ↔ USDT",
        "email_body": "<p>Пишу в последний раз — если тема неактуальна, просто дайте знать.</p><p>Если же у ваших клиентов есть потребность в конвертации рублей, давайте обсудим — возможно, это будет полезно для обеих сторон.</p>"
    },
]

# English sequences with {{first_name}}
EN_SEQUENCES_WITH_NAME = [
    {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "Partnership: RUB ↔ USDT conversion for your clients",
        "email_body": "<p>Hi {{first_name}},</p><p>We're Deliryo — a platform for RUB ↔ USDT conversion designed for high-net-worth clients.</p><p>If any of your clients need ruble conversion, we can be your technology partner with competitive rates and fast execution.</p><p>Would you be open to a quick chat?</p>"
    },
    {
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "Re: Partnership: RUB ↔ USDT conversion for your clients",
        "email_body": "<p>Hi {{first_name}}, just wanted to follow up on my previous email.</p><p>We work with family offices, wealth managers, and investment firms — providing fast RUB ↔ USDT conversion at competitive rates.</p><p>Happy to discuss if relevant.</p>"
    },
    {
        "seq_number": 3,
        "seq_delay_details": {"delay_in_days": 5},
        "subject": "Re: Re: Partnership: RUB ↔ USDT conversion for your clients",
        "email_body": "<p>Hi {{first_name}}, last follow-up — if this isn't relevant, just let me know.</p><p>If your clients do need ruble conversion, I'd love to explore a partnership. Either way, appreciate your time.</p>"
    },
]


async def main():
    async with async_session_maker() as session:
        # Check if rules already exist
        existing = await session.execute(
            select(CampaignPushRule).where(CampaignPushRule.project_id == 18)
        )
        if existing.scalars().first():
            print("Rules already exist for project 18, skipping seed")
            return

        # Get email account IDs (first 10)
        api_key = os.environ.get('SMARTLEAD_API_KEY')
        email_account_ids = []
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                'https://server.smartlead.ai/api/v1/email-accounts',
                params={'api_key': api_key}
            )
            if r.status_code == 200:
                accounts = r.json()
                if isinstance(accounts, list):
                    email_account_ids = [acc['id'] for acc in accounts[:10]]
        print(f"Using {len(email_account_ids)} email accounts")

        schedule = {
            "timezone": "Europe/Moscow",
            "days_of_the_week": [1, 2, 3, 4, 5],
            "start_hour": "09:00",
            "end_hour": "18:00",
            "min_time_btw_emails": 5,
            "max_new_leads_per_day": 50,
        }

        settings_config = {
            "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
            "stop_lead_settings": "REPLY_TO_AN_EMAIL",
            "send_as_plain_text": False,
            "follow_up_percentage": 100,
        }

        # Rule 1: Russian names (Cyrillic first_name)
        rule1 = CampaignPushRule(
            company_id=1,
            project_id=18,
            name="Russian + name",
            description="Russian-speaking contacts with a personal name. Uses Russian sequences with {{first_name}}.",
            language="ru",
            has_first_name=True,
            campaign_name_template="Deliryo {date} Из РФ",
            sequence_language="ru",
            sequence_template=RU_SEQUENCES_WITH_NAME,
            use_first_name_var=True,
            email_account_ids=email_account_ids,
            schedule_config=schedule,
            campaign_settings=settings_config,
            max_leads_per_campaign=500,
            priority=10,
            is_active=True,
        )

        # Rule 2: No name (generic emails like info@, contact@)
        rule2 = CampaignPushRule(
            company_id=1,
            project_id=18,
            name="No name (generic email)",
            description="Generic emails (info@, contact@, etc.) without personal name. Russian sequences without {{first_name}}.",
            language="any",
            has_first_name=False,
            campaign_name_template="Deliryo {date} Из РФ БЕЗ ИМЕНИ",
            sequence_language="ru",
            sequence_template=RU_SEQUENCES_NO_NAME,
            use_first_name_var=False,
            email_account_ids=email_account_ids,
            schedule_config=schedule,
            campaign_settings=settings_config,
            max_leads_per_campaign=500,
            priority=20,  # Higher priority — check generic first
            is_active=True,
        )

        # Rule 3: English names (Latin first_name)
        rule3 = CampaignPushRule(
            company_id=1,
            project_id=18,
            name="English + name",
            description="English-speaking contacts with a personal name. English sequences with {{first_name}}.",
            language="en",
            has_first_name=True,
            campaign_name_template="Deliryo {date} Из РФ Англ имена",
            sequence_language="en",
            sequence_template=EN_SEQUENCES_WITH_NAME,
            use_first_name_var=True,
            email_account_ids=email_account_ids,
            schedule_config=schedule,
            campaign_settings=settings_config,
            max_leads_per_campaign=500,
            priority=5,
            is_active=True,
        )

        session.add_all([rule1, rule2, rule3])
        await session.commit()
        print("Seeded 3 Deliryo push rules!")
        
        # Verify
        result = await session.execute(
            select(CampaignPushRule).where(CampaignPushRule.project_id == 18)
        )
        for r in result.scalars().all():
            print(f"  #{r.id} | {r.name} | lang={r.language} | has_name={r.has_first_name} | priority={r.priority}")


asyncio.run(main())
