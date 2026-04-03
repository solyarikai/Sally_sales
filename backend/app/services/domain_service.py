"""
Domain Service — Global domain registry with trash filtering and dedup.
Replaces parser/scrapers/domain_registry.py + core.py TrashFilter.
"""
from typing import List, Dict, Set, Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import csv
import io
import logging

from app.models.domain import Domain, DomainStatus, DomainSource

logger = logging.getLogger(__name__)


# ============ Load blacklist from Deliryo blacklist.db export ============

def _load_blacklist_file() -> Set[str]:
    """Load the blacklist domains from the exported text file."""
    blacklist_path = Path(__file__).parent / "blacklist_domains.txt"
    domains = set()
    if blacklist_path.exists():
        with open(blacklist_path, "r") as f:
            for line in f:
                d = line.strip().lower()
                if d:
                    domains.add(d)
        logger.info(f"Loaded {len(domains)} blacklist domains from {blacklist_path}")
    else:
        logger.warning(f"Blacklist file not found: {blacklist_path}")
    return domains

# Loaded once at module import time
BLACKLIST_DOMAINS: Set[str] = _load_blacklist_file()


# ============ Trash patterns ported from parser/scrapers/core.py ============

BASE_TRASH: Set[str] = {
    "ya.ru", "yandex.ru", "google.com", "avito.ru", "vk.com", "dzen.ru",
    "youtube.com", "prian.ru", "tranio.ru", "cian.ru", "rbc.ru", "wikipedia.org",
    "tinkoff.ru", "sberbank.ru", "domclick.ru", "hh.ru", "mvideo.ru",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "reddit.com", "pinterest.com", "tiktok.com", "ok.ru", "mail.ru", "t.me",
}

TRASH_PATTERNS: List[str] = [
    # Social networks
    "t.me", "telegram", "vk.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com", "ok.ru",
    "linkedin.com", "pinterest.com", "reddit.com",
    # News sites
    "news.ru", "ria.ru", "lenta.ru", "rbc.ru", "kommersant", "forbes",
    "interfax", "tass.com", "rt.com", "gazeta", "vedomosti", "iz.ru",
    # Crypto exchanges
    "binance.com", "bybit.com", "coinmarketcap", "coingecko",
    "coinbase.com", "kraken.com", "okx.com", "kucoin.com", "mexc.com",
    "tradingview.com", "cointelegraph", "coindesk",
    # Banks RU
    "banki.ru", "tbank.ru", "vtb.ru", "sberbank", "raiffeisen",
    "alfabank", "tinkoff", "gazprombank",
    # Real estate aggregators
    "tranio.", "realting.com", "homesoverseas", "prian.", "cian.ru",
    "domclick", "avito.ru", "etagi.com",
    # Travel aggregators
    "booking.com", "agoda.com", "tripadvisor", "airbnb",
    "trip.com", "tophotels", "pegast.ru", "tez-tour",
    # Search engines & wikis
    "wikipedia.org", "wiki.", "yandex.ru", "google.com", "dzen.ru",
    # Payment processors
    "wise.com", "revolut.com", "stripe.com", "paypal",
]


def normalize_domain(raw: str) -> str:
    """
    Normalize a domain string.
    Strips protocol, paths, query params, www prefix. Lowercases.
    """
    d = raw.strip().lower()
    if not d:
        return ""

    # If it looks like a URL, parse it
    if "://" in d:
        parsed = urlparse(d)
        d = parsed.hostname or d
    elif "/" in d:
        d = d.split("/")[0]

    # Strip trailing dot
    d = d.rstrip(".")

    # Strip www.
    if d.startswith("www."):
        d = d[4:]

    return d


def matches_trash_pattern(domain: str) -> bool:
    """Check if domain matches any hardcoded trash pattern or Deliryo blacklist."""
    d = domain.lower()
    if d in BASE_TRASH:
        return True
    if d in BLACKLIST_DOMAINS:
        return True
    for pattern in TRASH_PATTERNS:
        if pattern in d:
            return True
    return False


class DomainService:
    """
    Global domain registry service.
    All methods accept AsyncSession for DB operations.
    """

    async def add_domain(
        self,
        session: AsyncSession,
        raw_domain: str,
        status: DomainStatus = DomainStatus.ACTIVE,
        source: DomainSource = DomainSource.MANUAL,
    ) -> Optional[Domain]:
        """Add a single domain. Returns existing if duplicate."""
        domain_str = normalize_domain(raw_domain)
        if not domain_str:
            return None

        # Auto-detect trash
        if status == DomainStatus.ACTIVE and matches_trash_pattern(domain_str):
            status = DomainStatus.TRASH

        existing = await session.execute(
            select(Domain).where(Domain.domain == domain_str)
        )
        existing_domain = existing.scalar_one_or_none()

        if existing_domain:
            existing_domain.times_seen += 1
            existing_domain.last_seen = datetime.utcnow()
            return existing_domain

        new_domain = Domain(
            domain=domain_str,
            status=status,
            source=source,
        )
        session.add(new_domain)
        return new_domain

    async def is_trash(self, session: AsyncSession, raw_domain: str) -> bool:
        """Check if a domain is trash (by pattern or DB status)."""
        domain_str = normalize_domain(raw_domain)
        if not domain_str:
            return True

        if matches_trash_pattern(domain_str):
            return True

        result = await session.execute(
            select(Domain.status).where(Domain.domain == domain_str)
        )
        row = result.scalar_one_or_none()
        if row == DomainStatus.TRASH:
            return True

        return False

    async def is_known(self, session: AsyncSession, raw_domain: str) -> bool:
        """Check if a domain already exists in the registry."""
        domain_str = normalize_domain(raw_domain)
        if not domain_str:
            return False
        result = await session.execute(
            select(func.count()).where(Domain.domain == domain_str)
        )
        return (result.scalar() or 0) > 0

    async def check_domains(
        self,
        session: AsyncSession,
        raw_domains: List[str],
    ) -> List[Dict[str, str]]:
        """
        Check a batch of domains against the registry.
        Returns list of {domain, status} where status is 'new', 'known', or 'trash'.
        """
        results = []
        seen_in_batch: Set[str] = set()

        for raw in raw_domains:
            domain_str = normalize_domain(raw)
            if not domain_str:
                continue

            # Trash by pattern
            if matches_trash_pattern(domain_str):
                results.append({"domain": domain_str, "status": "trash"})
                continue

            # Duplicate within this batch
            if domain_str in seen_in_batch:
                results.append({"domain": domain_str, "status": "known"})
                continue
            seen_in_batch.add(domain_str)

            # Check DB
            existing = await session.execute(
                select(Domain).where(Domain.domain == domain_str)
            )
            db_domain = existing.scalar_one_or_none()

            if db_domain:
                if db_domain.status == DomainStatus.TRASH:
                    results.append({"domain": domain_str, "status": "trash"})
                else:
                    results.append({"domain": domain_str, "status": "known"})
            else:
                results.append({"domain": domain_str, "status": "new"})

        return results

    async def filter_domains(
        self,
        session: AsyncSession,
        raw_domains: List[str],
        source: DomainSource = DomainSource.SEARCH_GOOGLE,
        dry_run: bool = False,
    ) -> Dict[str, List[str]]:
        """
        Filter and persist a list of domains.
        Returns {"new": [...], "trash": [...], "duplicate": [...]}.
        New domains are automatically added to the registry.
        """
        new_domains: List[str] = []
        trash_domains: List[str] = []
        duplicate_domains: List[str] = []
        seen_in_batch: Set[str] = set()

        for raw in raw_domains:
            domain_str = normalize_domain(raw)
            if not domain_str:
                continue

            # Trash by pattern
            if matches_trash_pattern(domain_str):
                trash_domains.append(domain_str)
                if not dry_run:
                    existing = await session.execute(
                        select(func.count()).where(Domain.domain == domain_str)
                    )
                    if (existing.scalar() or 0) == 0:
                        session.add(Domain(
                            domain=domain_str,
                            status=DomainStatus.TRASH,
                            source=source,
                        ))
                continue

            # Batch dedup
            if domain_str in seen_in_batch:
                duplicate_domains.append(domain_str)
                continue
            seen_in_batch.add(domain_str)

            # DB check
            existing = await session.execute(
                select(Domain).where(Domain.domain == domain_str)
            )
            db_domain = existing.scalar_one_or_none()

            if db_domain:
                if db_domain.status == DomainStatus.TRASH:
                    trash_domains.append(domain_str)
                else:
                    duplicate_domains.append(domain_str)
                    if not dry_run:
                        db_domain.times_seen += 1
                        db_domain.last_seen = datetime.utcnow()
            else:
                new_domains.append(domain_str)
                if not dry_run:
                    session.add(Domain(
                        domain=domain_str,
                        status=DomainStatus.ACTIVE,
                        source=source,
                    ))

        return {
            "new": new_domains,
            "trash": trash_domains,
            "duplicate": duplicate_domains,
        }

    async def get_stats(self, session: AsyncSession) -> Dict[str, int]:
        """Get domain registry statistics."""
        total = (await session.execute(
            select(func.count(Domain.id))
        )).scalar() or 0

        active = (await session.execute(
            select(func.count(Domain.id)).where(Domain.status == DomainStatus.ACTIVE)
        )).scalar() or 0

        trash = (await session.execute(
            select(func.count(Domain.id)).where(Domain.status == DomainStatus.TRASH)
        )).scalar() or 0

        return {"total": total, "active": active, "trash": trash}

    async def export_domains_csv(
        self,
        session: AsyncSession,
        status_filter: Optional[DomainStatus] = None,
        source_filter: Optional[DomainSource] = None,
    ) -> str:
        """Export domains to CSV with single 'domain' column."""
        query = select(Domain)

        if status_filter:
            query = query.where(Domain.status == status_filter)
        if source_filter:
            query = query.where(Domain.source == source_filter)

        query = query.order_by(Domain.domain)

        result = await session.execute(query)
        domains = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["domain"])

        for domain in domains:
            writer.writerow([domain.domain])

        return output.getvalue()


# Module-level singleton
domain_service = DomainService()
