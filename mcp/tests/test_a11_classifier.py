"""Test A11 classifier on all 6 segments — does it correctly identify specific vs broad?"""
import asyncio, sys, json
sys.path.insert(0, "/app")
from app.services.industry_classifier import classify_industry_specificity
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select

TESTS = [
    ("Fashion brands in Italy", "Branded resale platform for fashion brands", ["apparel & fashion", "luxury goods & jewelry", "textiles"]),
    ("IT consulting companies in Miami", "Payroll for companies hiring internationally", ["information technology & services", "management consulting"]),
    ("Video production companies in London", "Payroll for companies hiring internationally", ["marketing & advertising", "media production", "motion pictures & film"]),
    ("IT consulting companies in US", "Payroll for companies hiring internationally", ["information technology & services", "management consulting"]),
    ("Video production companies in UK", "Payroll for companies hiring internationally", ["marketing & advertising", "media production", "motion pictures & film"]),
    ("Social media influencer agencies in UK", "AI social media management platform", ["marketing & advertising", "public relations & communications", "online media"]),
]

async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "openai", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        key = decrypt_value(row.api_key_encrypted).strip()

    print(f"{'Query':<45} {'Strategy':<18} {'Specific':<30} {'Broad'}")
    print("-" * 120)

    for query, offer, industries in TESTS:
        result = await classify_industry_specificity(query, offer, industries, key)
        specific = result.get("specific_industries", [])
        broad = result.get("broad_industries", [])
        strategy = result.get("recommendation", "?")
        print(f"{query:<45} {strategy:<18} {str(specific):<30} {broad}")
        print(f"  Reason: {result.get('reason', '')}")

asyncio.run(main())
