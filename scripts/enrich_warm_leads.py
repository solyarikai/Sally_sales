"""
Enrich warm EasyStaff Global leads with Apollo company data.
HARD MAX: 200 credits. Prioritizes meeting_request > interested > question.

Run on Hetzner: cd ~/magnum-opus-project/repo && python scripts/enrich_warm_leads.py
"""
import asyncio
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

CREDIT_HARD_MAX = 200
PROJECT_ID = 9

async def main():
    from sqlalchemy import select, text, func
    from app.db.database import async_session_maker
    from app.services.apollo_service import ApolloService

    apollo = ApolloService()
    credits_used = 0
    results = {}
    errors = []

    async with async_session_maker() as session:
        # Get all unique domains from warm replies, prioritized by warmth
        rows = (await session.execute(text("""
            SELECT DISTINCT ON (domain) domain, category, lead_company
            FROM (
                SELECT
                    split_part(pr.lead_email, '@', 2) as domain,
                    pr.category,
                    pr.lead_company,
                    CASE pr.category
                        WHEN 'meeting_request' THEN 0
                        WHEN 'interested' THEN 1
                        WHEN 'question' THEN 2
                    END as priority
                FROM processed_replies pr
                JOIN projects p ON p.id = :pid
                WHERE pr.campaign_name = ANY(SELECT jsonb_array_elements_text(p.campaign_filters))
                  AND pr.category IN ('interested', 'meeting_request', 'question')
                  AND pr.parent_reply_id IS NULL
                  AND pr.lead_email IS NOT NULL
                  AND pr.lead_email LIKE '%@%'
                  AND split_part(pr.lead_email, '@', 2) NOT IN (
                      'gmail.com','yahoo.com','hotmail.com','outlook.com',
                      'icloud.com','mail.com','protonmail.com','aol.com',
                      'linkedin.placeholder'
                  )
                ORDER BY split_part(pr.lead_email, '@', 2), priority, pr.received_at DESC
            ) sub
            ORDER BY domain, priority
        """), {"pid": PROJECT_ID})).fetchall()

        domains = [(r[0], r[1], r[2]) for r in rows]
        print(f"Found {len(domains)} unique company domains to enrich")
        print(f"Credit hard max: {CREDIT_HARD_MAX}")
        print()

        for domain, category, company in domains:
            if credits_used >= CREDIT_HARD_MAX:
                print(f"\n⚠️  HARD MAX REACHED ({CREDIT_HARD_MAX} credits). Stopping.")
                break

            try:
                print(f"[{credits_used+1}/{len(domains)}] Enriching {domain}...", end=" ", flush=True)
                data = await apollo.enrich_organization(domain)
                credits_used += 1

                if data and isinstance(data, dict) and data.get("name"):
                    results[domain] = {
                        "name": data.get("name", ""),
                        "industry": data.get("industry", ""),
                        "keywords": data.get("keywords", []),
                        "estimated_num_employees": data.get("estimated_num_employees"),
                        "annual_revenue_printed": data.get("annual_revenue_printed", ""),
                        "founded_year": data.get("founded_year"),
                        "city": data.get("city", ""),
                        "country": data.get("country", ""),
                        "linkedin_url": data.get("linkedin_url", ""),
                        "technologies": data.get("technologies", []),
                        "website_url": data.get("website_url", ""),
                    }
                    kw = ", ".join(results[domain]["keywords"][:5]) if results[domain]["keywords"] else "none"
                    print(f"✅ {results[domain]['industry']} | {results[domain]['estimated_num_employees']} emp | {kw}")
                else:
                    results[domain] = {"name": company or domain, "not_found": True}
                    print(f"❌ Not found in Apollo")

                # Rate limit: ~2/sec to stay under 200/min
                await asyncio.sleep(0.5)

            except Exception as e:
                credits_used += 1
                errors.append((domain, str(e)))
                print(f"❌ Error: {e}")

        # Save results
        output_path = "/tmp/apollo_enrichment_results.json"
        with open(output_path, "w") as f:
            json.dump({
                "credits_used": credits_used,
                "domains_enriched": len(results),
                "domains_not_found": sum(1 for v in results.values() if v.get("not_found")),
                "errors": errors,
                "data": results,
            }, f, indent=2, default=str)

        print(f"\n{'='*60}")
        print(f"Credits used: {credits_used}/{CREDIT_HARD_MAX}")
        print(f"Domains enriched: {len(results)}")
        print(f"Not found: {sum(1 for v in results.values() if v.get('not_found'))}")
        print(f"Errors: {len(errors)}")
        print(f"Results saved to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
