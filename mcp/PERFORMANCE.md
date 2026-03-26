# MCP Performance Metrics

Measured via real MCP SSE protocol (not API shortcuts).

## Connection & Protocol

| Operation | Latency | Notes |
|-----------|---------|-------|
| SSE Connect | ~12ms | Raw TCP to Hetzner |
| MCP Initialize | **4ms** | Protocol handshake |
| Tools list (30 tools) | **8ms** | All tool definitions |

## SmartLead Operations

| Operation | Latency | Notes |
|-----------|---------|-------|
| List campaigns (search "petr") | **1,104ms** | Fetches all from SmartLead API, filters locally |
| Import 13 campaigns as blacklist | **1,535ms** | SmartLead fetch + DB insert per campaign |
| **Full onboarding (connect → list → import)** | **~2.7s** | Acceptable for one-time setup |

## Apollo Gathering

| Operation | Latency | Notes |
|-----------|---------|-------|
| Gather 50 companies (2 pages) | ~4s | 2 Apollo API calls |
| Gather 25 companies (1 page) | ~2s | 1 Apollo API call |

## Pipeline Operations

| Operation | Latency | Notes |
|-----------|---------|-------|
| Blacklist check | <100ms | DB-only |
| Pre-filter | <100ms | DB-only |
| Scrape 50 websites | ~30s | Parallel HTTP, 0.3s rate limit |
| GPT analysis (50 companies) | ~60s | GPT-4o-mini, sequential |
| GPT analysis (100 companies) | ~120s | GPT-4o-mini, sequential |
| Sequence generation (5 steps) | ~3s | GPT-4o-mini single call |

## SmartLead Push

| Operation | Latency | Notes |
|-----------|---------|-------|
| Create DRAFT campaign | ~800ms | SmartLead API |
| Set sequences | ~500ms | SmartLead API |

## Bottlenecks

1. **GPT analysis is sequential** — could be parallelized (5-10 concurrent calls) to cut time 5-10x
2. **SmartLead list_campaigns** fetches ALL then filters — could cache or paginate
3. **Scraping** is already parallel (50 concurrent) — limited by rate limiting

## Cost per Pipeline Run (100 companies)

| Step | Time | Cost |
|------|------|------|
| Apollo (4 pages) | 4s | 4 credits |
| Scraping | 30s | $0 |
| GPT analysis | 120s | $0.30 |
| FindyMail (30 targets × 3) | 90s | $0.90 |
| Sequence gen | 3s | $0.003 |
| **Total** | **~4 min** | **~$1.20** |
