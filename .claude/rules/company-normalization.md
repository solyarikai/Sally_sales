# Company Name Normalization Rules

**ALWAYS apply these rules when:**
- User asks to normalize company names (in chat or via script)
- Loading leads into SmartLead (via MCP `mcp__smartlead__*`, API, or pipeline)
- Loading leads into Google Sheets (via MCP `mcp__google-sheets__*` or script)
- Any CSV/data prep that includes a `company_name` field

**Never skip normalization** for these operations even if not explicitly asked.

Source of truth: `sofia/scripts/bace/pipeline.py` → `normalize_company()` (mirrored in `magnum-opus/scripts/sofia/bace/pipeline.py`)

## Logic (in order)

1. **Strip + collapse spaces** — `re.sub(r"\s+", " ", name).strip()`
2. **Override table** — exact case-insensitive replacements (see `_COMPANY_OVERRIDES`)
3. **Mixed-case → leave as-is** — if name has both upper and lower letters, it's an intentional brand (HypeAuditor, iMagency, AdQuadrant) — don't touch
4. **All-lower or all-upper → Title Case** with exceptions:
   - `_UPPER_WORDS` stay uppercase: AI, API, B2B, PR, SEO, LLC, LTD, INC, UK, US, USA, UAE, EU, APAC, EMEA, LATAM, KOL, UGC, KPI, SaaS, CRM, DTC, MCN, IM, MCM, NFC, ROI, SMB, SME, SMM, IMC, GDP, ESG, CFO, CMO, COO, CPO, CTO, CEO, LLP
   - `_LOWER_WORDS` stay lowercase when not first/last word: a, an, the, and, but, or, nor, for, so, yet, at, by, in, of, on, to, up, as, is, via, with, from

## Override Table

| Input (case-insensitive) | Output |
|--------------------------|--------|
| imagency / immagency | iMagency |
| sideqik | Sideqik |
| traackr | Traackr |
| grin | GRIN |
| mavrck | Mavrck |
| tagger | Tagger |
| klear | Klear |
| heepsy | Heepsy |
| lefty | Lefty |
| modash | Modash |
| hypeauditor | HypeAuditor |
| upfluence | Upfluence |
| aspire | Aspire |
| captiv8 | Captiv8 |
| creator.co | Creator.co |
| socialbakers | Socialbakers |
| sociallypowerful | Socially Powerful |
| ykone | Ykone |
| whalar | Whalar |
| samy alliance | SAMY Alliance |
| webedia | Webedia |
| billion dollar boy | Billion Dollar Boy |
| influencer | Influencer |
| viral nation | Viral Nation |
| ogilvy | Ogilvy |

## What NOT to normalize

- Mixed-case brands (e.g. `HypeAuditor`, `AdQuadrant`, `TikTok`) — already intentional
- Names with digits or special chars in brand position (e.g. `Captiv8`, `Creator.co`)
- Names from `_COMPANY_OVERRIDES` — already handled

## When to apply

- Pipeline upload → SmartLead (auto via `normalize_company()`)
- Manual SmartLead normalization → `sofia/scripts/normalize_company_names.py`
- Google Sheets import tab → `sofia/scripts/normalize_sheets.py` → `normalize_company_name()`
