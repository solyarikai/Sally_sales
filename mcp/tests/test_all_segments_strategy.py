"""Test filter_mapper strategy for all 6 segments — which get industry_tag_ids?"""
import asyncio, sys, json
sys.path.insert(0, "/app")

SEGMENTS = [
    ("Fashion brands in Italy", "TFP builds branded resale platforms for fashion brands"),
    ("IT consulting companies in Miami", "EasyStaff provides payroll for companies hiring internationally"),
    ("Video production companies in London", "EasyStaff provides payroll for companies hiring internationally"),
    ("IT consulting companies in US", "EasyStaff provides payroll for companies hiring internationally"),
    ("Video production companies in UK", "EasyStaff provides payroll for companies hiring internationally"),
    ("Social media influencer agencies in UK", "OnSocial is an AI-powered social media management platform"),
]

async def main():
    from app.services.filter_mapper import map_query_to_filters
    from app.db import async_session_maker
    from app.models.integration import MCPIntegrationSetting
    from app.services.encryption import decrypt_value
    from sqlalchemy import select

    # Get OpenAI key
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "openai", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        openai_key = decrypt_value(row.api_key_encrypted).strip() if row else ""

    print(f"{'Segment':<45} {'Strategy':<18} {'Tag IDs':>8} {'Keywords':>8} {'Industries'}")
    print("-" * 110)

    for query, offer in SEGMENTS:
        try:
            result = await map_query_to_filters(query, offer, openai_key)
            strategy = result.get("filter_strategy", "?")
            tag_ids = result.get("organization_industry_tag_ids") or []
            keywords = result.get("q_organization_keyword_tags", [])
            industries = result.get("industries", [])
            print(f"{query:<45} {strategy:<18} {len(tag_ids):>8} {len(keywords):>8} {industries}")
        except Exception as e:
            print(f"{query:<45} ERROR: {str(e)[:60]}")

asyncio.run(main())
