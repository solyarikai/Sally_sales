"""
Phase 1 company scraper — wraps apollo_universal_search.js Puppeteer script.
Searches Apollo Companies UI (FREE, no credits) for DACH/Nordic companies
with keywords indicating LATAM/international remote team presence.

One browser session per country, all LATAM keywords searched together.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path("/app/scripts/apollo_universal_search.js")
OUTPUT_DIR = Path("/app/gathering-data/dach")

# One Puppeteer session per location (7 sessions total)
SEARCH_LOCATIONS = [
    "Germany",
    "Austria",
    "Switzerland",
    "Sweden",
    "Netherlands",
    "Norway",
    "Finland",
]

# Keywords indicating LATAM/international team presence
# All searched in one browser session per location
LATAM_KEYWORDS = [
    "LATAM",
    "Latin America",
    "nearshore",
    "remote team",
    "distributed team",
    "global team",
    "offshore",
]

SIZE_RANGES = ["10,50", "51,200", "201,500"]

# Pages per keyword/size combo (3 pages × ~25 companies = ~75 per combo)
MAX_PAGES_PER_SEARCH = 3


async def scrape_dach_companies(
    on_progress: Optional[Callable] = None,
) -> List[dict]:
    """
    Scrape Apollo Companies UI for DACH companies with LATAM/international keywords.
    Returns deduplicated list of dicts: domain, name, employees, hq_country, industry.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SCRIPT_PATH.exists():
        raise RuntimeError(f"Puppeteer script not found at {SCRIPT_PATH}. Check volume mount.")

    all_companies: dict = {}  # domain → data (deduplicates across countries)

    for location in SEARCH_LOCATIONS:
        if on_progress:
            await on_progress({
                "phase": "phase1",
                "current_location": location,
                "keywords": LATAM_KEYWORDS,
                "companies_found": len(all_companies),
            })

        output_file = f"dach_{location.lower().replace(' ', '_')}_companies.json"
        output_path = OUTPUT_DIR / output_file

        args = [
            "node", str(SCRIPT_PATH),
            "--location", location,
            "--keywords", ",".join(LATAM_KEYWORDS),
            "--max-pages", str(MAX_PAGES_PER_SEARCH),
            "--output-dir", str(OUTPUT_DIR),
            "--output-file", output_file,
        ]
        for size in SIZE_RANGES:
            args.extend(["--sizes", size])

        # Resume if partial output exists from previous attempt
        if output_path.exists():
            args.append("--resume")
            logger.info(f"Resuming {location} (existing output found)")

        logger.info(
            f"[Phase1] Scraping {location} | "
            f"keywords={LATAM_KEYWORDS} | sizes={SIZE_RANGES}"
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/app",
            )
            # 1h timeout per location (7 keywords × 3 sizes × 3 pages = lots of scraping)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3600)

            stdout_text = stdout.decode()
            stderr_text = stderr.decode()

            if stderr_text:
                logger.warning(f"  stderr ({location}): {stderr_text[-500:]}")

            if proc.returncode != 0:
                logger.error(
                    f"  Scraper failed for {location} "
                    f"(rc={proc.returncode}): {stderr_text[:300]}"
                )
                continue

            if output_path.exists():
                with open(output_path) as f:
                    raw = json.load(f)

                before = len(all_companies)
                for item in raw:
                    domain = (item.get("domain") or "").lower().strip()
                    domain = domain.replace("www.", "").rstrip("/")
                    if not domain or "." not in domain:
                        continue
                    if domain not in all_companies:
                        all_companies[domain] = {
                            "domain": domain,
                            "name": item.get("name", ""),
                            "employees": item.get("employees"),
                            "industry": item.get("industry", ""),
                            "hq_country": location,
                            "linkedin_url": item.get("linkedin_url", ""),
                        }

                new_unique = len(all_companies) - before
                logger.info(
                    f"  {location}: {len(raw)} scraped → "
                    f"{new_unique} new unique domains | "
                    f"{len(all_companies)} total"
                )
            else:
                logger.warning(f"  No output file after scrape: {output_path}")

        except asyncio.TimeoutError:
            logger.error(f"  Scraper timed out for {location} (1h limit exceeded)")
        except Exception as e:
            logger.error(f"  Scraper error for {location}: {e}", exc_info=True)

        await asyncio.sleep(3)  # brief pause between countries

    logger.info(f"[Phase1] Scrape complete: {len(all_companies)} unique DACH companies")
    return list(all_companies.values())
