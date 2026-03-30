#!/usr/bin/env python3
"""Scrape ALL remaining unscraped companies for project 9."""
import sys
import asyncio
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

COMMIT_EVERY = 25
FLUSH_INTERVAL = 30  # seconds


async def main():
    from app.db import async_session_maker, init_db
    from app.services.scraper_service import scraper_service
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select, update, not_
    from datetime import datetime, timezone

    await init_db()

    # Get ALL unscraped companies for project 9
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.scraped_text.is_(None),
                DiscoveredCompany.scraped_at.is_(None),  # never attempted
                DiscoveredCompany.status != DiscoveredCompanyStatus.REJECTED,
                not_(DiscoveredCompany.domain.like('%_apollo_%')),
                DiscoveredCompany.domain.isnot(None),
                DiscoveredCompany.domain != '',
            )
        )
        companies = result.all()

    total = len(companies)
    print(f"Scraping {total} companies - 50 concurrent, commit every {COMMIT_EVERY} or {FLUSH_INTERVAL}s")

    urls = [{'row_id': c.id, 'url': f'https://{c.domain}'} for c in companies]

    success_count = 0
    fail_count = 0
    batch_buffer = []
    last_flush = time.time()

    async def flush_buffer():
        nonlocal success_count, batch_buffer, last_flush
        if not batch_buffer:
            return
        async with async_session_maker() as s:
            for r in batch_buffer:
                await s.execute(
                    update(DiscoveredCompany)
                    .where(DiscoveredCompany.id == r['row_id'])
                    .values(
                        scraped_text=r['text'][:50000],
                        scraped_at=datetime.now(timezone.utc),
                    )
                )
            await s.commit()
            success_count += len(batch_buffer)
            rate = success_count / max(1, time.time() - start_time) * 60
            print(f"  OK: {success_count}/{total} | Failed: {fail_count} | Rate: {rate:.0f}/min")
            batch_buffer.clear()
            last_flush = time.time()

    async def on_result(result):
        nonlocal batch_buffer, fail_count
        if result.get('success') and result.get('text'):
            batch_buffer.append(result)
        else:
            fail_count += 1

        if len(batch_buffer) >= COMMIT_EVERY or (time.time() - last_flush > FLUSH_INTERVAL and batch_buffer):
            await flush_buffer()

    start_time = time.time()
    await scraper_service.scrape_batch(
        urls, timeout=15, max_concurrent=50, delay_between_requests=0.05,
        on_result=on_result,
    )

    # Final flush
    await flush_buffer()

    # Mark all remaining unscraped as attempted (so we don't retry dead domains)
    async with async_session_maker() as s:
        await s.execute(
            update(DiscoveredCompany)
            .where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.scraped_text.is_(None),
                DiscoveredCompany.scraped_at.is_(None),
                DiscoveredCompany.id.in_([c.id for c in companies]),
            )
            .values(scraped_at=datetime.now(timezone.utc))
        )
        await s.commit()

    elapsed = time.time() - start_time
    print(f"\nDONE in {elapsed/60:.1f}min: {success_count} succeeded, {fail_count} failed out of {total}")


if __name__ == "__main__":
    asyncio.run(main())
