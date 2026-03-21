# Apollo Credits — What Costs Money, What's Free

## CRITICAL: Almost ALL Apollo API endpoints cost credits

### Endpoints that COST credits (NEVER use without approval)
| Endpoint | Cost | Used by |
|----------|------|---------|
| `/mixed_companies/search` | Credits per page | `apollo.companies.api` adapter — **MUST BE DISABLED** |
| `/mixed_people/search` | Credits per page | People search API |
| `/organizations/enrich` | 1 credit per call | `enrich_organization()` in apollo_service |
| `/people/match` | 1 credit per call | People enrichment |
| Any `/search` endpoint | Credits per page | All search APIs |

### What's actually FREE
| Method | Cost | Notes |
|--------|------|-------|
| Puppeteer UI scraping (Companies Tab) | $0 | Scrapes DOM/intercepts browser API — no credits |
| Puppeteer UI scraping (People Tab) | $0 | Same — browser automation, not API |
| Apollo login/auth | $0 | Just authentication |

### Current credit status
- Account: `danila@getsally.io` / `UQdzDShCjAi5Nil!!`
- API key: `9yIx...WVqA`
- Status: **INSUFFICIENT CREDITS** (as of March 21, 2026)
- Credits burned by mistake: ~25 (runs #64-68 used `/mixed_companies/search`)

## Incident: March 21, 2026

### What happened
1. Puppeteer scraper blocked by Cloudflare after scraping NYC + LA
2. Tried `apollo.companies.api` adapter as alternative
3. Assumed `/mixed_companies/search` was free — IT'S NOT
4. Launched 10 cities via API — 5 succeeded before credits ran out
5. ~75 companies returned, ~25 credits burned

### Root cause
- `apollo_service.search_organizations()` had NO "costs credits" warning
- `enrich_organization()` had the warning but `search_organizations()` didn't
- Adapter was named `apollo.companies.api` suggesting it was an official free endpoint

### Fix applied
- `apollo.companies.api` adapter MUST NOT be used without explicit operator approval
- Added to CLAUDE.md: all Apollo API endpoints cost credits
- Only Puppeteer emulators are free

## Puppeteer Cloudflare Problem

### What happens
After scraping 2-3 cities, Cloudflare Turnstile blocks subsequent Puppeteer sessions:
- Login succeeds
- Page navigation succeeds
- But a Cloudflare "Verification failed" dialog appears
- No data loads — 0 companies extracted

### Solution: Residential Proxy
Use Apify residential proxy for Puppeteer browser connections.
- Already configured: `APIFY_PROXY_PASSWORD` set on Hetzner
- Rotates IP per session — Cloudflare can't fingerprint
- Must be added to Puppeteer launch args, not just httpx

### Proxy config
```javascript
// Puppeteer with Apify residential proxy
const browser = await puppeteer.launch({
  headless: 'new',
  args: [
    '--no-sandbox',
    '--proxy-server=http://proxy.apify.com:8000',
  ],
});
// Authenticate proxy per page
await page.authenticate({
  username: 'groups-RESIDENTIAL,session-apollo_' + Date.now(),
  password: process.env.APIFY_PROXY_PASSWORD,
});
```
