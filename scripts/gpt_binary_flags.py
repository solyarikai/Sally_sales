#!/usr/bin/env python3
"""
GPT-4o-mini Binary Flag Detection — company classification for corridor scoring.

RULE: NEVER ask GPT for numerical scores (hallucination: 87% scored >=70).
Only asks YES/NO binary flags + vertical classification + 1-sentence reasoning.

One prompt per company. All flags in single call. ~$0.0002 per company.
Results cached — re-runs skip already-analyzed domains.

Output: /tmp/{corridor}_v7_gpt_flags.json

Usage (inside Docker on server):
  python3 scripts/gpt_binary_flags.py uae-pakistan
  python3 scripts/gpt_binary_flags.py au-philippines
  python3 scripts/gpt_binary_flags.py arabic-southafrica
"""
import asyncio
import json
import os
import sys
import time

SCRAPE_CACHE = '/tmp/uae_pk_v6_scrape.json'
DEEP_SCRAPE_CACHE = '/tmp/deep_scrape_v7.json'

CORRIDOR_PARAMS = {
    'uae-pakistan': {
        'buyer_country': 'UAE',
        'talent_country': 'Pakistan',
        'talent_country_key': 'pakistan',
    },
    'au-philippines': {
        'buyer_country': 'Australia',
        'talent_country': 'Philippines',
        'talent_country_key': 'philippines',
    },
    'arabic-southafrica': {
        'buyer_country': 'Gulf states (Qatar, Saudi Arabia, UAE, Bahrain, Kuwait, Oman)',
        'talent_country': 'South Africa',
        'talent_country_key': 'south_africa',
    },
}


def build_prompt(company_name, domain, text, buyer_country, talent_country, talent_key):
    return f"""You analyze company websites for a B2B sales tool that helps {buyer_country} companies pay contractors in {talent_country}.

COMPANY: {company_name}
DOMAIN: {domain}
WEBSITE:
{text[:2000]}

Classify this company. Answer ONLY in JSON, no other text:
{{
  "red_flags": {{
    "hq_in_{talent_key}": true/false,
    "has_{talent_key}_office": true/false,
    "is_construction_realestate": true/false,
    "is_hospitality_tourism": true/false,
    "is_enterprise_500plus": true/false
  }},
  "green_flags": {{
    "mentions_outsourcing_bpo": true/false,
    "mentions_contractors_freelancers": true/false,
    "mentions_remote_teams": true/false,
    "has_{talent_key}_workforce": true/false
  }},
  "company_vertical": "tech|fintech|saas|staffing|outsourcing|consulting|digital_agency|ecommerce|healthcare|logistics|trading|manufacturing|other",
  "what_they_do": "1 sentence",
  "employee_estimate": null,
  "reasoning": "1 sentence: why this company would or would NOT need to pay {talent_country} contractors"
}}"""


def get_best_text(domain, scrape_data, deep_data):
    """Combine homepage + deep scrape pages into best available text."""
    parts = []

    # Homepage from main scrape cache
    sd = scrape_data.get(domain, {})
    if sd.get('status') == 'ok' and sd.get('text'):
        parts.append(sd['text'])

    # Deep scrape pages (about, contact, team, locations)
    dd = deep_data.get(domain, {})
    if dd.get('pages'):
        for page_type in ['about', 'contact', 'team', 'locations']:
            page = dd['pages'].get(page_type, {})
            if page.get('text'):
                parts.append(page['text'])

    return '\n\n'.join(parts)[:2000]


async def main():
    import httpx

    if len(sys.argv) < 2:
        print("Usage: python3 gpt_binary_flags.py <corridor>")
        print("Corridors: uae-pakistan, au-philippines, arabic-southafrica")
        return

    corridor = sys.argv[1]
    if corridor not in CORRIDOR_PARAMS:
        print(f"Unknown corridor: {corridor}")
        return

    params = CORRIDOR_PARAMS[corridor]
    slug = corridor.replace('-', '_')
    cache_file = f'/tmp/{slug}_v7_gpt_flags.json'

    # Load existing cache
    gpt_cache = {}
    if os.path.exists(cache_file):
        gpt_cache = json.load(open(cache_file))
        print(f"Loaded GPT cache: {len(gpt_cache)} domains")

    # Load website data
    scrape_data = {}
    if os.path.exists(SCRAPE_CACHE):
        scrape_data = json.load(open(SCRAPE_CACHE))
        print(f"Loaded scrape cache: {len(scrape_data)} domains")

    deep_data = {}
    if os.path.exists(DEEP_SCRAPE_CACHE):
        deep_data = json.load(open(DEEP_SCRAPE_CACHE))
        print(f"Loaded deep scrape cache: {len(deep_data)} domains")

    # Get domains from analysis CSV
    import csv
    csv_file = f'/tmp/{slug}_v7_company_analysis.csv'
    if not os.path.exists(csv_file):
        csv_file = '/tmp/uae_pakistan_v7_company_analysis.csv'
        if not os.path.exists(csv_file):
            print("No analysis CSV found. Run scoring first.")
            return

    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    # Build work queue: domains with text that aren't cached
    to_analyze = []
    for r in rows:
        domain = r.get('domain', '').strip()
        if not domain or domain in gpt_cache:
            continue
        text = get_best_text(domain, scrape_data, deep_data)
        if len(text) > 100:
            to_analyze.append((domain, r.get('company', domain), text))

    print(f"Domains to analyze: {len(to_analyze)} (skipping {len(gpt_cache)} cached)")
    if not to_analyze:
        print("All domains already in cache.")
        return

    # OpenAI API
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return

    sem = asyncio.Semaphore(25)
    ok = errors = retries = 0
    t0 = time.time()

    async def analyze_one(client, domain, company, text):
        nonlocal ok, errors, retries
        prompt = build_prompt(
            company, domain, text,
            params['buyer_country'], params['talent_country'], params['talent_country_key']
        )
        async with sem:
            for attempt in range(3):
                try:
                    resp = await client.post(
                        'https://api.openai.com/v1/chat/completions',
                        json={
                            'model': 'gpt-4o-mini',
                            'messages': [{'role': 'user', 'content': prompt}],
                            'temperature': 0.1,
                            'max_tokens': 300,
                        },
                        timeout=30.0,
                    )
                    if resp.status_code == 200:
                        content = resp.json()['choices'][0]['message']['content'].strip()
                        # Strip markdown fences
                        if content.startswith('```'):
                            content = content.split('\n', 1)[1] if '\n' in content else content[3:]
                            content = content.rsplit('```', 1)[0]
                        result = json.loads(content.strip())
                        gpt_cache[domain] = result
                        ok += 1
                        return
                    elif resp.status_code == 429:
                        retries += 1
                        await asyncio.sleep(3 * (attempt + 1))
                    else:
                        errors += 1
                        return
                except json.JSONDecodeError:
                    errors += 1
                    return
                except Exception:
                    if attempt < 2:
                        retries += 1
                        await asyncio.sleep(2)
                    else:
                        errors += 1

    async with httpx.AsyncClient(
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        verify=False,
    ) as client:
        batch_size = 100
        for i in range(0, len(to_analyze), batch_size):
            batch = to_analyze[i:i + batch_size]
            await asyncio.gather(*[analyze_one(client, d, c, t) for d, c, t in batch])
            elapsed = time.time() - t0
            print(f"  [{i + len(batch)}/{len(to_analyze)}] "
                  f"{ok} ok, {errors} err, {retries} retries | {elapsed:.0f}s")

            # Save after each batch
            with open(cache_file, 'w') as f:
                json.dump(gpt_cache, f, ensure_ascii=False, indent=2)

    # Cost estimate
    cost_input = ok * 800 * 0.00000015
    cost_output = ok * 150 * 0.0000006
    total_cost = cost_input + cost_output

    print(f"\nDone: {ok} analyzed, {errors} errors, {retries} retries in {time.time() - t0:.0f}s")
    print(f"Estimated cost: ${total_cost:.2f}")
    print(f"Total in cache: {len(gpt_cache)} domains")
    print(f"Saved to: {cache_file}")


if __name__ == '__main__':
    asyncio.run(main())
