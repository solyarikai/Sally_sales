"""Test real-world concurrency limits for Apify and OpenAI.

Run on Hetzner inside mcp-backend container:
  docker exec mcp-backend python /app/tests/test_concurrency_limits.py

Logs all results to /app/tests/tmp/concurrency_test_{timestamp}.txt
"""
import asyncio
import time
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, "/app")

# ── Config ──
APIFY_PASSWORD = os.environ.get("APIFY_PROXY_PASSWORD", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Test domains for scraping
TEST_DOMAINS = [
    "stripe.com", "shopify.com", "hubspot.com", "slack.com", "notion.so",
    "figma.com", "linear.app", "vercel.com", "supabase.com", "planetscale.com",
    "railway.app", "render.com", "fly.io", "neon.tech", "turso.tech",
    "clerk.com", "resend.com", "inngest.com", "trigger.dev", "unkey.dev",
    "upstash.com", "convex.dev", "sanity.io", "contentful.com", "strapi.io",
    "ghost.org", "webflow.com", "framer.com", "builder.io", "plasmic.app",
    "retool.com", "appsmith.com", "tooljet.com", "budibase.com", "baserow.io",
    "airtable.com", "coda.io", "monday.com", "asana.com", "clickup.com",
    "todoist.com", "linear.app", "height.app", "shortcut.com", "phabricator.com",
    "sentry.io", "datadog.com", "grafana.com", "newrelic.com", "honeycomb.io",
    "loki.grafana.com", "elastic.co", "splunk.com", "dynatrace.com", "logz.io",
]  # 50 domains

RESULTS_DIR = "/app/tests/tmp"
os.makedirs(RESULTS_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"{RESULTS_DIR}/concurrency_test_{TIMESTAMP}.txt"


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S.%f')[:12]}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ═══════════════════════════════════════════
# TEST 1: APIFY SCRAPER CONCURRENCY
# ═══════════════════════════════════════════

async def test_apify_concurrency(concurrency: int, domains: list):
    """Test Apify residential proxy at given concurrency. Returns success rate + timing."""
    import httpx
    import random

    if not APIFY_PASSWORD:
        log(f"  SKIP: No APIFY_PROXY_PASSWORD set")
        return {"concurrency": concurrency, "skip": True}

    sem = asyncio.Semaphore(concurrency)
    results = {"success": 0, "fail_429": 0, "fail_timeout": 0, "fail_other": 0, "times": []}

    async def fetch_one(domain):
        async with sem:
            session_id = f"test_{random.randint(10000, 99999)}"
            proxy = f"http://groups-RESIDENTIAL,session-{session_id}:{APIFY_PASSWORD}@proxy.apify.com:8000"
            url = f"https://{domain}"
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15), proxy=proxy, verify=True, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    elapsed = time.time() - start
                    results["times"].append(elapsed)
                    if resp.status_code == 429:
                        results["fail_429"] += 1
                    elif resp.status_code >= 400:
                        results["fail_other"] += 1
                    else:
                        results["success"] += 1
            except httpx.TimeoutException:
                results["fail_timeout"] += 1
                results["times"].append(time.time() - start)
            except Exception as e:
                results["fail_other"] += 1
                results["times"].append(time.time() - start)

    start_all = time.time()
    await asyncio.gather(*[fetch_one(d) for d in domains])
    total_time = time.time() - start_all

    avg_time = sum(results["times"]) / len(results["times"]) if results["times"] else 0
    total = len(domains)

    log(f"  APIFY concurrency={concurrency}: {results['success']}/{total} success, "
        f"{results['fail_429']} 429s, {results['fail_timeout']} timeouts, {results['fail_other']} other errors. "
        f"Total: {total_time:.1f}s, Avg: {avg_time:.2f}s/req")

    return {
        "concurrency": concurrency,
        "total": total,
        "success": results["success"],
        "fail_429": results["fail_429"],
        "fail_timeout": results["fail_timeout"],
        "fail_other": results["fail_other"],
        "total_seconds": round(total_time, 2),
        "avg_seconds": round(avg_time, 2),
        "success_rate": round(results["success"] / total * 100, 1),
    }


# ═══════════════════════════════════════════
# TEST 2: OPENAI CONCURRENCY (GPT-4o-mini)
# ═══════════════════════════════════════════

async def test_openai_concurrency(concurrency: int, count: int):
    """Test OpenAI GPT-4o-mini at given concurrency. Returns timing + rate."""
    import httpx

    if not OPENAI_KEY:
        log(f"  SKIP: No OPENAI_API_KEY set")
        return {"concurrency": concurrency, "skip": True}

    sem = asyncio.Semaphore(concurrency)
    results = {"success": 0, "fail_429": 0, "fail_other": 0, "times": [], "tokens": []}

    prompt = "Classify this company as TARGET or NOT_TARGET for a payroll service: Stripe is a payment processing platform. Reply with ONE word: TARGET or NOT_TARGET"

    async def call_one(i):
        async with sem:
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 10,
                            "temperature": 0,
                        },
                    )
                    elapsed = time.time() - start
                    results["times"].append(elapsed)
                    if resp.status_code == 429:
                        results["fail_429"] += 1
                    elif resp.status_code >= 400:
                        results["fail_other"] += 1
                    else:
                        results["success"] += 1
                        data = resp.json()
                        tokens = data.get("usage", {}).get("total_tokens", 0)
                        results["tokens"].append(tokens)
            except Exception as e:
                results["fail_other"] += 1
                results["times"].append(time.time() - start)

    start_all = time.time()
    await asyncio.gather(*[call_one(i) for i in range(count)])
    total_time = time.time() - start_all

    avg_time = sum(results["times"]) / len(results["times"]) if results["times"] else 0
    rpm = (results["success"] / total_time * 60) if total_time > 0 else 0

    log(f"  OPENAI concurrency={concurrency}: {results['success']}/{count} success, "
        f"{results['fail_429']} 429s, {results['fail_other']} other. "
        f"Total: {total_time:.1f}s, Avg: {avg_time:.2f}s/req, RPM: {rpm:.0f}")

    return {
        "concurrency": concurrency,
        "total": count,
        "success": results["success"],
        "fail_429": results["fail_429"],
        "fail_other": results["fail_other"],
        "total_seconds": round(total_time, 2),
        "avg_seconds": round(avg_time, 2),
        "effective_rpm": round(rpm),
        "success_rate": round(results["success"] / count * 100, 1),
    }


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

async def main():
    log("=" * 60)
    log("CONCURRENCY LIMIT TEST — Apify + OpenAI")
    log("=" * 60)

    all_results = {"apify": [], "openai": []}

    # ── Apify tests: 10, 25, 50, 75, 100 concurrent ──
    log("\n── APIFY RESIDENTIAL PROXY ──")
    for c in [10, 25, 50, 75, 100]:
        log(f"\nTesting Apify with {c} concurrent requests ({len(TEST_DOMAINS)} domains)...")
        r = await test_apify_concurrency(c, TEST_DOMAINS)
        all_results["apify"].append(r)
        await asyncio.sleep(2)  # cool down between tests

    # ── OpenAI tests: 10, 25, 50, 75, 100 concurrent ──
    log("\n── OPENAI GPT-4o-mini ──")
    for c in [10, 25, 50, 75, 100]:
        count = min(c * 2, 100)  # test 2x concurrent or max 100
        log(f"\nTesting OpenAI with {c} concurrent requests ({count} total calls)...")
        r = await test_openai_concurrency(c, count)
        all_results["openai"].append(r)
        await asyncio.sleep(2)

    # ── Summary ──
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)

    log("\nApify Results:")
    log(f"{'Concurrent':>10} {'Success%':>10} {'429s':>6} {'Timeouts':>10} {'Total(s)':>10} {'Avg(s)':>8}")
    for r in all_results["apify"]:
        if r.get("skip"): continue
        log(f"{r['concurrency']:>10} {r['success_rate']:>9}% {r['fail_429']:>6} {r['fail_timeout']:>10} {r['total_seconds']:>10} {r['avg_seconds']:>8}")

    log("\nOpenAI Results:")
    log(f"{'Concurrent':>10} {'Success%':>10} {'429s':>6} {'RPM':>6} {'Total(s)':>10} {'Avg(s)':>8}")
    for r in all_results["openai"]:
        if r.get("skip"): continue
        log(f"{r['concurrency']:>10} {r['success_rate']:>9}% {r['fail_429']:>6} {r['effective_rpm']:>6} {r['total_seconds']:>10} {r['avg_seconds']:>8}")

    # Save JSON results
    json_file = f"{RESULTS_DIR}/concurrency_results_{TIMESTAMP}.json"
    with open(json_file, "w") as f:
        json.dump(all_results, f, indent=2)
    log(f"\nResults saved to: {json_file}")
    log(f"Log saved to: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
