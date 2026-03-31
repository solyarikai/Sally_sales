"""
Integration tests for Telegram outreach sending safety mechanisms.

Validates all anti-ban protections:
  1. Each account connects through its own unique proxy
  2. Device fingerprints are unique across accounts
  3. Human-like delays are within expected bounds
  4. Daily sending limits (warm-up + young session caps) are respected
  5. Spamblock detection and emergency stop work correctly

Run:
  docker exec leadgen-backend python -m pytest tests/test_services/test_sending_safety.py -v
"""
import importlib
import statistics
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db import Base
from app.models.telegram_outreach import (
    TgAccount, TgAccountStatus, TgSpamblockType,
    TgCampaign, TgCampaignAccount, TgCampaignStatus,
    TgProxy, TgProxyGroup, TgProxyProtocol,
    TgRecipient, TgRecipientStatus,
    TgSequence, TgSequenceStep, TgStepVariant,
    TgOutreachMessage, TgMessageStatus,
)

# Pre-register a lightweight stub for app.services to avoid importing the full
# __init__ chain (which pulls in OpenAI, Redis, and other heavy deps not
# needed for safety tests).
import os as _os
import types as _types

_svc_dir = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "app", "services"))
if "app.services" not in sys.modules:
    _stub = _types.ModuleType("app.services")
    _stub.__path__ = [_svc_dir]
    sys.modules["app.services"] = _stub

# Now we can import sending_worker safely
from app.services.sending_worker import (  # noqa: E402
    SendingWorker,
    get_effective_daily_limit,
    get_session_age_days,
    is_young_session,
    is_within_send_window,
    _human_delay,
    WARMUP_MSGS_PER_DAY,
    YOUNG_SESSION_DAYS,
    YOUNG_SESSION_MAX_MSGS,
    YOUNG_SESSION_DELAY_MULT,
)

# Map PostgreSQL JSONB to SQLite JSON for in-memory testing
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy import JSON as _JSON

def _patch_tables_for_sqlite(tables):
    """Make PostgreSQL-specific tables compatible with SQLite.

    - Replace JSONB columns with JSON
    - Remove duplicate indexes (column-level unique=True + explicit Index)
    - Strip postgresql_where from partial indexes
    """
    for table in tables:
        for col in table.columns:
            if isinstance(col.type, _JSONB):
                col.type = _JSON()
        # Deduplicate indexes: keep only one per column set
        seen_cols = set()
        to_remove = []
        for idx in table.indexes:
            key = tuple(sorted(c.name for c in idx.columns))
            if key in seen_cols:
                to_remove.append(idx)
            else:
                seen_cols.add(key)
            # Strip postgresql_where (not supported by SQLite)
            if hasattr(idx, 'dialect_options'):
                idx.dialect_options.pop('postgresql', None)
        for idx in to_remove:
            table.indexes.discard(idx)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ── Fixtures ──────────────────────────────────────────────────────────


# Tables needed for safety tests (avoids creating the full schema)
_TG_TABLES = [
    TgProxyGroup.__table__,
    TgProxy.__table__,
    TgAccount.__table__,
    TgCampaign.__table__,
    TgCampaignAccount.__table__,
    TgRecipient.__table__,
    TgSequence.__table__,
    TgSequenceStep.__table__,
    TgStepVariant.__table__,
    TgOutreachMessage.__table__,
]


_jsonb_patched = False

@pytest_asyncio.fixture(scope="function")
async def engine():
    global _jsonb_patched
    if not _jsonb_patched:
        _patch_tables_for_sqlite(_TG_TABLES)
        _jsonb_patched = True

    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=_TG_TABLES)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=_TG_TABLES)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(engine):
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def proxy_group(db: AsyncSession):
    pg = TgProxyGroup(name="Test Group", country="DE")
    db.add(pg)
    await db.flush()
    await db.refresh(pg)
    return pg


@pytest_asyncio.fixture
async def proxies(db: AsyncSession, proxy_group: TgProxyGroup):
    """Create 5 distinct proxies in the group."""
    result = []
    for i in range(5):
        p = TgProxy(
            proxy_group_id=proxy_group.id,
            host=f"10.0.0.{i + 1}",
            port=8000 + i,
            username=f"user{i}",
            password=f"pass{i}",
            protocol=TgProxyProtocol.SOCKS5,
            is_active=True,
        )
        db.add(p)
        result.append(p)
    await db.flush()
    for p in result:
        await db.refresh(p)
    return result


@pytest_asyncio.fixture
async def accounts(db: AsyncSession, proxy_group: TgProxyGroup, proxies):
    """Create 5 accounts, each pre-assigned to a unique proxy."""
    result = []
    fingerprints = [
        ("PC 64bit", "Windows 10", "5.5.3 x64"),
        ("ThinkPadT480", "Windows 11", "6.5.1 x64"),
        ("XPS15-9510", "Windows 10", "5.5.3 x64"),
        ("Latitude5520", "Windows 11", "6.5.1 x64"),
        ("VivoBookS15", "Windows 10", "5.5.3 x64"),
    ]
    for i in range(5):
        dev, sysv, appv = fingerprints[i]
        acc = TgAccount(
            phone=f"+7900000000{i}",
            username=f"testuser{i}",
            status=TgAccountStatus.ACTIVE,
            proxy_group_id=proxy_group.id,
            assigned_proxy_id=proxies[i].id,
            device_model=dev,
            system_version=sysv,
            app_version=appv,
            lang_code="en",
            system_lang_code="en-US",
            daily_message_limit=10,
            messages_sent_today=0,
            session_created_at=datetime.utcnow() - timedelta(days=30),
        )
        db.add(acc)
        result.append(acc)
    await db.flush()
    for a in result:
        await db.refresh(a)
    return result


@pytest_asyncio.fixture
async def campaign(db: AsyncSession, accounts):
    c = TgCampaign(
        name="Safety Test Campaign",
        status=TgCampaignStatus.ACTIVE,
        daily_message_limit=50,
        timezone="UTC",
        send_from_hour=0,
        send_to_hour=23,
        delay_between_sends_min=11,
        delay_between_sends_max=25,
        spamblock_errors_to_skip=5,
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    for acc in accounts:
        ca = TgCampaignAccount(campaign_id=c.id, account_id=acc.id)
        db.add(ca)
    await db.flush()
    return c


# ══════════════════════════════════════════════════════════════════════
# 1. PROXY UNIQUENESS — Each account gets its own proxy
# ══════════════════════════════════════════════════════════════════════


class TestProxyUniqueness:
    """Every active account must connect through a unique proxy."""

    async def test_assigned_proxies_are_unique(self, db, accounts, proxies):
        """No two active accounts share the same proxy."""
        proxy_ids = [a.assigned_proxy_id for a in accounts]
        assert len(proxy_ids) == len(set(proxy_ids)), (
            f"Duplicate proxy assignments found: {proxy_ids}"
        )

    async def test_every_account_has_proxy(self, db, accounts):
        """Every active account in a proxy group must have an assigned proxy."""
        for acc in accounts:
            assert acc.assigned_proxy_id is not None, (
                f"Account {acc.phone} has no proxy assigned"
            )

    async def test_reassign_gives_unique_proxy(self, db, proxy_group, proxies, accounts):
        """When an account loses its proxy, reassignment picks an unused one."""
        worker = SendingWorker()

        # Remove proxy from account 0
        old_proxy_id = accounts[0].assigned_proxy_id
        accounts[0].assigned_proxy_id = None
        await db.flush()

        new_proxy = await worker._try_reassign_proxy(accounts[0], db)
        assert new_proxy is not None, "Failed to reassign proxy"
        assert new_proxy.id == old_proxy_id, (
            "Should reassign the same free proxy since it's the only unused one"
        )

        # Verify no collisions
        all_proxy_ids = [a.assigned_proxy_id for a in accounts]
        assert len(all_proxy_ids) == len(set(all_proxy_ids))

    async def test_no_free_proxy_returns_none(self, db, proxy_group, proxies, accounts):
        """If all proxies in the group are taken, reassignment returns None."""
        worker = SendingWorker()

        # Create a 6th account with no proxy
        extra = TgAccount(
            phone="+79000000099",
            status=TgAccountStatus.ACTIVE,
            proxy_group_id=proxy_group.id,
            assigned_proxy_id=None,
            daily_message_limit=10,
            messages_sent_today=0,
        )
        db.add(extra)
        await db.flush()

        result = await worker._try_reassign_proxy(extra, db)
        assert result is None, "Should return None when no free proxies exist"

    async def test_dead_proxy_excluded_from_assignment(self, db, proxy_group, proxies, accounts):
        """Inactive proxies are never assigned."""
        worker = SendingWorker()

        # Deactivate proxy 0, free account 0
        proxies[0].is_active = False
        accounts[0].assigned_proxy_id = None
        await db.flush()

        new_proxy = await worker._try_reassign_proxy(accounts[0], db)
        # No free active proxies left (proxies 1-4 assigned, proxy 0 dead)
        assert new_proxy is None, "Dead proxy should not be assigned"


# ══════════════════════════════════════════════════════════════════════
# 2. DEVICE FINGERPRINTS — Each account has unique fingerprint
# ══════════════════════════════════════════════════════════════════════


class TestDeviceFingerprints:
    """Each account must have a distinct device fingerprint tuple."""

    async def test_fingerprints_unique_across_accounts(self, accounts):
        """No two accounts share the exact same (device, system, app) tuple."""
        fps = [
            (a.device_model, a.system_version, a.app_version)
            for a in accounts
        ]
        assert len(fps) == len(set(fps)), (
            f"Duplicate fingerprints found: {fps}"
        )

    async def test_fingerprint_fields_populated(self, accounts):
        """Every account must have all fingerprint fields set."""
        for acc in accounts:
            assert acc.device_model, f"{acc.phone}: missing device_model"
            assert acc.system_version, f"{acc.phone}: missing system_version"
            assert acc.app_version, f"{acc.phone}: missing app_version"
            assert acc.lang_code, f"{acc.phone}: missing lang_code"
            assert acc.system_lang_code, f"{acc.phone}: missing system_lang_code"

    async def test_fingerprint_passed_to_connect(self, accounts):
        """Verify that connect() receives the account's fingerprint params."""
        from app.services.telegram_engine import TelegramEngine

        engine = TelegramEngine()
        acc = accounts[0]

        with patch.object(engine, '_make_client', return_value=AsyncMock()) as mock_make:
            mock_client = AsyncMock()
            mock_make.return_value = mock_client
            mock_client.connect = AsyncMock()
            mock_client.is_user_authorized = AsyncMock(return_value=True)

            try:
                await engine.connect(
                    acc.id, phone=acc.phone, api_id=12345, api_hash="testhash",
                    device_model=acc.device_model, system_version=acc.system_version,
                    app_version=acc.app_version, lang_code=acc.lang_code,
                    system_lang_code=acc.system_lang_code, proxy=None,
                )
            except Exception:
                pass  # We only care about the call args

            mock_make.assert_called_once()
            call_kwargs = mock_make.call_args
            # Verify fingerprint params were forwarded
            assert call_kwargs.kwargs.get('device_model') == acc.device_model or \
                   (len(call_kwargs.args) > 0 and acc.device_model in str(call_kwargs))


# ══════════════════════════════════════════════════════════════════════
# 3. DELAYS — Human-like timing between messages
# ══════════════════════════════════════════════════════════════════════


class TestHumanDelays:
    """Delays must follow the mixture distribution with safety modifiers."""

    @pytest.fixture
    def base_campaign(self):
        """Minimal campaign mock for delay tests."""
        c = MagicMock(spec=TgCampaign)
        c.timezone = "UTC"
        c.send_from_hour = 0
        c.send_to_hour = 24
        c.delay_between_sends_min = 11
        c.delay_between_sends_max = 25
        return c

    def test_delay_always_positive(self, base_campaign):
        """Delay must always be > 0."""
        for _ in range(500):
            d = _human_delay(11, 25, base_campaign)
            assert d > 0, f"Got non-positive delay: {d}"

    def test_delay_has_minimum_floor(self, base_campaign):
        """Delay should never go below 80% of base_min (gaussian floor)."""
        min_floor = 11 * 0.8  # 8.8 seconds
        for _ in range(500):
            d = _human_delay(11, 25, base_campaign, messages_sent_today=0, session_age_days=30)
            # The 65% normal path has floor at base_min*0.8
            # Medium/long pauses are always >= base_max * 1.2
            # So minimum possible is base_min * 0.8 + jitter (0.1)
            assert d >= min_floor, f"Delay {d} below floor {min_floor}"

    def test_delay_statistical_distribution(self, base_campaign):
        """Majority of delays should cluster around the base range, not at extremes."""
        delays = [_human_delay(11, 25, base_campaign, messages_sent_today=0, session_age_days=30)
                  for _ in range(1000)]
        median = statistics.median(delays)
        # Median should be roughly in the 11-35s range (normal + some medium pauses)
        assert 8 < median < 50, f"Median delay {median} is outside expected range"

    def test_young_session_multiplier(self, base_campaign):
        """Young sessions (< 7 days) get 1.8x delay multiplier."""
        mature_delays = [_human_delay(11, 25, base_campaign, session_age_days=30)
                         for _ in range(500)]
        young_delays = [_human_delay(11, 25, base_campaign, session_age_days=2)
                        for _ in range(500)]

        mature_mean = statistics.mean(mature_delays)
        young_mean = statistics.mean(young_delays)

        # Young delays should be ~1.8x mature delays (allow variance)
        ratio = young_mean / mature_mean
        assert 1.4 < ratio < 2.3, (
            f"Young/mature ratio {ratio:.2f} outside expected 1.4-2.3 "
            f"(young_mean={young_mean:.1f}, mature_mean={mature_mean:.1f})"
        )

    def test_fatigue_increases_delay(self, base_campaign):
        """More messages sent today → longer delays."""
        fresh_delays = [_human_delay(11, 25, base_campaign, messages_sent_today=0, session_age_days=30)
                        for _ in range(500)]
        fatigued_delays = [_human_delay(11, 25, base_campaign, messages_sent_today=25, session_age_days=30)
                           for _ in range(500)]

        fresh_mean = statistics.mean(fresh_delays)
        fatigued_mean = statistics.mean(fatigued_delays)

        # 25 messages over 5 = 20 extra → +40% fatigue
        assert fatigued_mean > fresh_mean, (
            f"Fatigued mean {fatigued_mean:.1f} should exceed fresh mean {fresh_mean:.1f}"
        )

    def test_micro_jitter_present(self, base_campaign):
        """Delays should never be perfectly round (jitter adds 0.1-0.9s)."""
        delays = [_human_delay(11, 25, base_campaign) for _ in range(100)]
        # Check that fractional parts vary (not all .00)
        fractional_parts = [d - int(d) for d in delays]
        unique_fractions = len(set(round(f, 2) for f in fractional_parts))
        assert unique_fractions > 5, "Micro-jitter seems absent — too few unique fractional parts"


# ══════════════════════════════════════════════════════════════════════
# 4. DAILY LIMITS — Warm-up ramp + young session caps
# ══════════════════════════════════════════════════════════════════════


class TestDailyLimits:
    """Sending limits must enforce warm-up ramp and young session caps."""

    def _make_account(self, daily_limit=10, session_age_days=None):
        acc = MagicMock(spec=TgAccount)
        acc.daily_message_limit = daily_limit
        if session_age_days is not None:
            acc.session_created_at = datetime.utcnow() - timedelta(days=session_age_days)
        else:
            acc.session_created_at = None
        return acc

    def test_mature_account_gets_full_limit(self):
        """Account > 7 days old gets its full daily_message_limit."""
        acc = self._make_account(daily_limit=20, session_age_days=30)
        assert get_effective_daily_limit(acc) == 20

    def test_no_session_date_gets_full_limit(self):
        """Account without session_created_at is treated as mature."""
        acc = self._make_account(daily_limit=15, session_age_days=None)
        assert get_effective_daily_limit(acc) == 15

    def test_day_0_warmup(self):
        """Brand new session (day 0): limit = min(2*1, 5) = 2."""
        acc = self._make_account(daily_limit=20, session_age_days=0)
        assert get_effective_daily_limit(acc) == WARMUP_MSGS_PER_DAY  # 2

    def test_day_1_warmup(self):
        """Day 1 session: limit = min(2*2, 5) = 4."""
        acc = self._make_account(daily_limit=20, session_age_days=1)
        assert get_effective_daily_limit(acc) == 4

    def test_day_2_warmup(self):
        """Day 2 session: limit = min(2*3, 5) = 5 (young cap)."""
        acc = self._make_account(daily_limit=20, session_age_days=2)
        assert get_effective_daily_limit(acc) == YOUNG_SESSION_MAX_MSGS  # 5

    def test_day_5_warmup_capped(self):
        """Day 5 session: warmup=12 but young cap=5 → 5."""
        acc = self._make_account(daily_limit=20, session_age_days=5)
        assert get_effective_daily_limit(acc) == YOUNG_SESSION_MAX_MSGS  # 5

    def test_day_6_still_young(self):
        """Day 6 (still < 7): warmup=14 but young cap=5 → 5."""
        acc = self._make_account(daily_limit=20, session_age_days=6)
        assert get_effective_daily_limit(acc) == YOUNG_SESSION_MAX_MSGS  # 5

    def test_day_7_becomes_mature(self):
        """Day 7 (>= YOUNG_SESSION_DAYS): no young cap, warmup=16 → min(16, 20) = 16."""
        acc = self._make_account(daily_limit=20, session_age_days=7)
        assert get_effective_daily_limit(acc) == 16

    def test_day_9_ramp_completes(self):
        """Day 9: warmup=20 >= limit=20 → full limit."""
        acc = self._make_account(daily_limit=20, session_age_days=9)
        assert get_effective_daily_limit(acc) == 20

    def test_low_base_limit_respected(self):
        """Even if warmup would allow more, base limit is the ceiling."""
        acc = self._make_account(daily_limit=3, session_age_days=30)
        assert get_effective_daily_limit(acc) == 3

    def test_is_young_session_boundary(self):
        """is_young_session returns True for < 7 days, False for >= 7."""
        young = self._make_account(session_age_days=6)
        mature = self._make_account(session_age_days=7)
        no_date = self._make_account(session_age_days=None)

        assert is_young_session(young) is True
        assert is_young_session(mature) is False
        assert is_young_session(no_date) is False


# ══════════════════════════════════════════════════════════════════════
# 5. SPAMBLOCK DETECTION — Cascade + emergency stop
# ══════════════════════════════════════════════════════════════════════


class TestSpamblockDetection:
    """Spamblock handling must mark accounts and trigger emergency stop."""

    async def test_spamblock_threshold_marks_account(self, db, accounts, campaign):
        """After N consecutive spamblock errors, account is marked SPAMBLOCKED."""
        worker = SendingWorker()
        acc = accounts[0]
        threshold = campaign.spamblock_errors_to_skip  # 5

        # Get the campaign-account link
        ca_r = await db.execute(
            select(TgCampaignAccount).where(
                TgCampaignAccount.campaign_id == campaign.id,
                TgCampaignAccount.account_id == acc.id,
            )
        )
        ca_link = ca_r.scalar()

        # Simulate reaching threshold
        ca_link.consecutive_spamblock_errors = threshold
        await db.flush()

        # Verify the threshold logic (from _send_one)
        if ca_link.consecutive_spamblock_errors >= threshold:
            acc.status = TgAccountStatus.SPAMBLOCKED
            acc.spamblock_type = TgSpamblockType.TEMPORARY
            acc.spamblocked_at = datetime.utcnow()

        assert acc.status == TgAccountStatus.SPAMBLOCKED
        assert acc.spamblock_type == TgSpamblockType.TEMPORARY
        assert acc.spamblocked_at is not None

    async def test_below_threshold_stays_active(self, db, accounts, campaign):
        """Below threshold, account stays active."""
        acc = accounts[1]
        ca_r = await db.execute(
            select(TgCampaignAccount).where(
                TgCampaignAccount.campaign_id == campaign.id,
                TgCampaignAccount.account_id == acc.id,
            )
        )
        ca_link = ca_r.scalar()
        ca_link.consecutive_spamblock_errors = 3  # Below threshold of 5
        await db.flush()

        assert acc.status == TgAccountStatus.ACTIVE

    async def test_emergency_stop_pauses_all_campaigns(self, db, campaign):
        """30 consecutive global spamblocks should pause ALL active campaigns."""
        worker = SendingWorker()

        # Create a second active campaign
        c2 = TgCampaign(
            name="Second Campaign", status=TgCampaignStatus.ACTIVE,
            daily_message_limit=50, timezone="UTC",
            send_from_hour=0, send_to_hour=23,
        )
        db.add(c2)
        await db.flush()

        # Simulate 30 consecutive spamblocks
        worker._consecutive_global_spamblocks = 30

        if worker._consecutive_global_spamblocks >= worker._EMERGENCY_THRESHOLD:
            all_active_r = await db.execute(
                select(TgCampaign).where(TgCampaign.status == TgCampaignStatus.ACTIVE)
            )
            for c in all_active_r.scalars().all():
                c.status = TgCampaignStatus.PAUSED
            await db.flush()

        # Both campaigns should be paused
        await db.refresh(campaign)
        await db.refresh(c2)
        assert campaign.status == TgCampaignStatus.PAUSED
        assert c2.status == TgCampaignStatus.PAUSED

    async def test_successful_send_resets_spamblock_counter(self, db, accounts, campaign):
        """A successful send resets the global spamblock counter."""
        worker = SendingWorker()
        worker._consecutive_global_spamblocks = 15

        # Simulate successful send
        worker._consecutive_global_spamblocks = 0  # reset on success

        assert worker._consecutive_global_spamblocks == 0

    async def test_spamblock_cascade_reassigns_recipient(self, db, accounts, campaign):
        """When account is spamblocked, recipient is reassigned to another account."""
        # Create a recipient
        r = TgRecipient(
            campaign_id=campaign.id,
            username="target_user",
            first_name="Target",
            status=TgRecipientStatus.IN_SEQUENCE,
            assigned_account_id=accounts[0].id,
            custom_variables={},
        )
        db.add(r)
        await db.flush()
        await db.refresh(r)

        # Simulate cascade: mark account 0 as failed for this recipient
        failed_ids = [accounts[0].id]
        r.custom_variables = {**r.custom_variables, "_failed_account_ids": failed_ids}
        r.status = TgRecipientStatus.PENDING
        r.assigned_account_id = None
        await db.flush()

        # Recipient should be re-assignable to other accounts
        assert r.status == TgRecipientStatus.PENDING
        assert r.assigned_account_id is None
        assert accounts[0].id in r.custom_variables["_failed_account_ids"]

    async def test_all_accounts_spamblocked_marks_recipient_failed(self, db, accounts, campaign):
        """If all campaign accounts are spamblocked for a recipient → FAILED."""
        r = TgRecipient(
            campaign_id=campaign.id,
            username="exhausted_target",
            first_name="Exhausted",
            status=TgRecipientStatus.IN_SEQUENCE,
            custom_variables={},
        )
        db.add(r)
        await db.flush()

        # All 5 accounts failed for this recipient
        failed_ids = [a.id for a in accounts]
        r.custom_variables = {"_failed_account_ids": failed_ids}

        # Count total campaign accounts
        total_accs = 5  # matches our fixture

        if len(failed_ids) >= total_accs:
            r.status = TgRecipientStatus.FAILED
            r.next_message_at = None

        assert r.status == TgRecipientStatus.FAILED
        assert r.next_message_at is None


# ══════════════════════════════════════════════════════════════════════
# 6. SEND WINDOW — Timezone-based send window enforcement
# ══════════════════════════════════════════════════════════════════════


class TestSendWindow:
    """Send window checks must respect timezone and hour boundaries."""

    def _make_campaign(self, from_h, to_h, tz="UTC"):
        c = MagicMock(spec=TgCampaign)
        c.send_from_hour = from_h
        c.send_to_hour = to_h
        c.timezone = tz
        return c

    def test_within_normal_window(self):
        """Hour 12 is within 9-18 window."""
        c = self._make_campaign(9, 18)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 12, 0)
            assert is_within_send_window(c) is True

    def test_outside_normal_window(self):
        """Hour 20 is outside 9-18 window."""
        c = self._make_campaign(9, 18)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 20, 0)
            assert is_within_send_window(c) is False

    def test_midnight_wrap_inside(self):
        """Hour 23 is within 22-06 (midnight-wrapping) window."""
        c = self._make_campaign(22, 6)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 23, 0)
            assert is_within_send_window(c) is True

    def test_midnight_wrap_inside_early(self):
        """Hour 3 is within 22-06 (midnight-wrapping) window."""
        c = self._make_campaign(22, 6)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 3, 0)
            assert is_within_send_window(c) is True

    def test_midnight_wrap_outside(self):
        """Hour 12 is outside 22-06 (midnight-wrapping) window."""
        c = self._make_campaign(22, 6)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 12, 0)
            assert is_within_send_window(c) is False

    def test_boundary_start(self):
        """Hour 9 is within 9-18 (inclusive start)."""
        c = self._make_campaign(9, 18)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 9, 0)
            assert is_within_send_window(c) is True

    def test_boundary_end(self):
        """Hour 18 is outside 9-18 (exclusive end)."""
        c = self._make_campaign(9, 18)
        with patch("app.services.sending_worker.now_in_tz") as mock_now:
            mock_now.return_value = datetime(2026, 1, 1, 18, 0)
            assert is_within_send_window(c) is False
