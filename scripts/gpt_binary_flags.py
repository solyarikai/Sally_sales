#!/usr/bin/env python3
"""
Company Binary Flag Classification for corridor scoring.

RULE: NEVER ask LLM for numerical scores (hallucination). Only YES/NO flags.

Supports: gpt-4o-mini, gemini-2.0-flash-001, gemini-2.5-pro

Output: /tmp/{corridor}_v8_gpt_flags.json

Usage:
  python3 scripts/gpt_binary_flags.py uae-pakistan                    # default: gpt-4o-mini
  python3 scripts/gpt_binary_flags.py uae-pakistan --model gemini     # gemini-2.0-flash
  python3 scripts/gpt_binary_flags.py uae-pakistan --model gemini-pro # gemini-2.5-pro
  python3 scripts/gpt_binary_flags.py uae-pakistan --test 10          # test on 10 domains
  python3 scripts/gpt_binary_flags.py uae-pakistan --fresh            # ignore cache, re-analyze all
"""
import asyncio
import json
import os
import sys
import time

# Allow running from /scripts/ inside Docker (app is at /app)
if os.path.isdir('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

SCRAPE_CACHE = '/tmp/uae_pk_v6_scrape.json'
DEEP_SCRAPE_CACHE = '/tmp/deep_scrape_v7.json'

CORRIDOR_PARAMS = {
    'uae-pakistan': {
        'buyer_country': 'UAE (United Arab Emirates)',
        'buyer_country_key': 'uae',
        'talent_country': 'Pakistan',
        'talent_country_key': 'pakistan',
    },
    'au-philippines': {
        'buyer_country': 'Australia',
        'buyer_country_key': 'australia',
        'talent_country': 'Philippines',
        'talent_country_key': 'philippines',
    },
    'arabic-southafrica': {
        'buyer_country': 'Gulf states (Qatar, Saudi Arabia, UAE, Bahrain, Kuwait, Oman)',
        'buyer_country_key': 'gulf',
        'talent_country': 'South Africa',
        'talent_country_key': 'south_africa',
    },
}


def build_prompt(company_name, domain, text, params):
    buyer = params['buyer_country']
    buyer_key = params['buyer_country_key']
    talent = params['talent_country']
    talent_key = params['talent_country_key']

    return f"""You classify companies for a B2B sales tool called EasyStaff.
EasyStaff helps companies in {buyer} pay their remote contractors and employees in {talent}.

Our IDEAL customer: a company HEADQUARTERED in {buyer} that has remote contractors or an offshore team in {talent}, size 5-200 employees.

NOT our customer:
- Companies headquartered in {talent} (they pay locally)
- Companies that PROVIDE payroll/EOR/HR services (they are our COMPETITORS)
- Companies that ARE an outsourcing/staffing agency selling {talent} labor to others
- Enterprises with 300+ employees (they have in-house HR/payroll)
- Construction, hospitality, food manufacturing, real estate companies

COMPANY: {company_name}
DOMAIN: {domain}
WEBSITE TEXT:
{text[:2000]}

Answer ONLY in valid JSON:
{{
  "hq_country": "the country where this company is headquartered (not branch offices)",
  "is_hq_in_{buyer_key}": true/false,
  "is_hq_in_{talent_key}": true/false,
  "is_competitor": true/false,
  "competitor_reason": "null or: payroll_provider / eor_provider / hr_outsourcing / staffing_agency",
  "is_outsourcing_provider": true/false,
  "is_construction_realestate_hospitality": true/false,
  "is_enterprise_300plus": true/false,
  "has_{talent_key}_workforce": true/false,
  "mentions_outsourcing_contractors": true/false,
  "company_vertical": "tech|fintech|saas|staffing|outsourcing|consulting|digital_agency|ecommerce|healthcare|logistics|trading|manufacturing|food|investment|other",
  "what_they_do": "1 sentence",
  "employee_estimate": null,
  "would_need_easystaff": true/false,
  "reasoning": "1 sentence why they would or would NOT need EasyStaff"
}}"""


def get_best_text(domain, scrape_data, deep_data):
    """Combine homepage + deep scrape pages into best available text."""
    parts = []
    sd = scrape_data.get(domain, {})
    if sd.get('status') == 'ok' and sd.get('text'):
        parts.append(sd['text'])
    dd = deep_data.get(domain, {})
    if dd.get('pages'):
        for page_type in ['about', 'contact', 'team', 'locations']:
            page = dd['pages'].get(page_type, {})
            if page.get('text'):
                parts.append(page['text'])
    return '\n\n'.join(parts)[:2000]


# ─── MODEL BACKENDS ──────────────────────────────────────────────────

async def call_openai(client, prompt, api_key):
    resp = await client.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1,
            'max_tokens': 400,
        },
        timeout=30.0,
    )
    if resp.status_code == 200:
        return resp.json()['choices'][0]['message']['content'].strip()
    elif resp.status_code == 429:
        return None  # rate limited
    else:
        raise Exception(f"OpenAI {resp.status_code}: {resp.text[:200]}")


async def call_gemini(client, prompt, api_key, model='gemini-2.0-flash-001'):
    resp = await client.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}',
        headers={'Content-Type': 'application/json'},
        json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.1,
                'maxOutputTokens': 400,
                'responseMimeType': 'application/json',
            },
        },
        timeout=30.0,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    elif resp.status_code == 429:
        return None
    else:
        raise Exception(f"Gemini {resp.status_code}: {resp.text[:200]}")


def parse_json_response(content):
    """Parse JSON from LLM response, handling markdown fences."""
    if not content:
        return None
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
        content = content.rsplit('```', 1)[0]
    return json.loads(content.strip())


async def main():
    import httpx

    if len(sys.argv) < 2:
        print("Usage: python3 gpt_binary_flags.py <corridor> [--model gpt|gemini|gemini-pro] [--test N] [--fresh]")
        return

    corridor = sys.argv[1]
    if corridor not in CORRIDOR_PARAMS:
        print(f"Unknown corridor: {corridor}")
        return

    params = CORRIDOR_PARAMS[corridor]
    slug = corridor.replace('-', '_')

    # Parse args
    model_name = 'gpt'
    test_limit = 0
    fresh = False
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == '--model' and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        elif args[i] == '--test' and i + 1 < len(args):
            test_limit = int(args[i + 1])
            i += 2
        elif args[i] == '--fresh':
            fresh = True
            i += 1
        else:
            i += 1

    cache_file = f'/tmp/{slug}_v8_gpt_flags.json'
    print(f"Model: {model_name} | Corridor: {corridor} | Cache: {cache_file}")

    # Load cache
    gpt_cache = {}
    if not fresh and os.path.exists(cache_file):
        gpt_cache = json.load(open(cache_file))
        print(f"Loaded cache: {len(gpt_cache)} domains")

    # Load website data
    scrape_data = {}
    if os.path.exists(SCRAPE_CACHE):
        scrape_data = json.load(open(SCRAPE_CACHE))
        print(f"Scrape cache: {len(scrape_data)} domains")

    deep_data = {}
    if os.path.exists(DEEP_SCRAPE_CACHE):
        deep_data = json.load(open(DEEP_SCRAPE_CACHE))
        print(f"Deep scrape: {len(deep_data)} domains")

    # Get domains from analysis CSV
    import csv
    csv_file = f'/tmp/{slug}_v7_company_analysis.csv'
    if not os.path.exists(csv_file):
        csv_file = '/tmp/uae_pakistan_v7_company_analysis.csv'
        if not os.path.exists(csv_file):
            print("No analysis CSV found.")
            return

    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    # Build work queue
    to_analyze = []
    for r in rows:
        domain = r.get('domain', '').strip()
        if not domain or (domain in gpt_cache and not fresh):
            continue
        text = get_best_text(domain, scrape_data, deep_data)
        if len(text) > 100:
            to_analyze.append((domain, r.get('company', domain), text))

    if test_limit:
        to_analyze = to_analyze[:test_limit]

    print(f"To analyze: {len(to_analyze)} (cached: {len(gpt_cache)})")
    if not to_analyze:
        print("Nothing to analyze.")
        return

    # API keys
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    gemini_key = os.environ.get('GEMINI_API_KEY', '')

    if model_name == 'gpt' and not openai_key:
        print("ERROR: OPENAI_API_KEY not set")
        return
    if model_name.startswith('gemini') and not gemini_key:
        print("ERROR: GEMINI_API_KEY not set")
        return

    sem = asyncio.Semaphore(25 if model_name == 'gpt' else 10)
    ok = errors = retries = 0
    t0 = time.time()

    async def analyze_one(client, domain, company, text):
        nonlocal ok, errors, retries
        prompt = build_prompt(company, domain, text, params)
        async with sem:
            for attempt in range(3):
                try:
                    if model_name == 'gpt':
                        content = await call_openai(client, prompt, openai_key)
                    elif model_name == 'gemini-pro':
                        content = await call_gemini(client, prompt, gemini_key, 'gemini-2.5-pro')
                    else:
                        content = await call_gemini(client, prompt, gemini_key, 'gemini-2.5-flash')

                    if content is None:  # rate limited
                        retries += 1
                        await asyncio.sleep(3 * (attempt + 1))
                        continue

                    result = parse_json_response(content)
                    if result:
                        gpt_cache[domain] = result
                        ok += 1
                        return
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

    async with httpx.AsyncClient(verify=False) as client:
        batch_size = 100 if model_name == 'gpt' else 50
        for i in range(0, len(to_analyze), batch_size):
            batch = to_analyze[i:i + batch_size]
            await asyncio.gather(*[analyze_one(client, d, c, t) for d, c, t in batch])
            elapsed = time.time() - t0
            rate = (i + len(batch)) / max(elapsed, 1)
            print(f"  [{i + len(batch)}/{len(to_analyze)}] "
                  f"{ok} ok, {errors} err, {retries} retry | {elapsed:.0f}s | {rate:.1f}/s")

            with open(cache_file, 'w') as f:
                json.dump(gpt_cache, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\nDone: {ok} ok, {errors} err, {retries} retry in {elapsed:.0f}s ({ok/max(elapsed,1):.1f}/s)")
    print(f"Total cached: {len(gpt_cache)}")
    print(f"Saved: {cache_file}")

    # Show sample results
    if ok > 0:
        print(f"\nSample results:")
        count = 0
        for domain, data in gpt_cache.items():
            if count >= 5:
                break
            hq = data.get('hq_country', '?')
            wneed = data.get('would_need_easystaff', '?')
            comp = data.get('is_competitor', False)
            vert = data.get('company_vertical', '?')
            reason = data.get('reasoning', '')[:80]
            print(f"  {domain}: HQ={hq} | need={wneed} | competitor={comp} | {vert} | {reason}")
            count += 1


if __name__ == '__main__':
    asyncio.run(main())
