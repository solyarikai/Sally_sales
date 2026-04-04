"""
Telegram Outreach API router.

Manages Telegram accounts, proxy groups, outreach campaigns,
message sequences, and recipients.
"""
import logging
import re as _re
from datetime import datetime as _dt, timedelta as _td
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select, func, desc, asc, delete as sa_delete, insert as sa_insert, and_, or_, text as sa_text, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db import get_session
from app.models.telegram_outreach import (
    TgAccount, TgAccountTag, TgAccountTagLink,
    TgProxyGroup, TgProxy,
    TgCampaign, TgCampaignAccount,
    TgRecipient, TgSequence, TgSequenceStep, TgStepVariant, TgOutreachMessage,
    TgAccountStatus, TgSpamblockType, TgCampaignStatus, TgCampaignType, TgRecipientStatus, TgMessageStatus,
    TgInboxDialog, TgContact, TgContactStatus,
    TgIncomingReply, TgBlacklist,
    TgWarmupLog, TgWarmupActionType, TgWarmupChannel,
    TgCrmCustomField, TgCrmCustomFieldType, TgCrmLeadFieldValue,
)
from app.models.telegram_dm import TelegramDMAccount

logger = logging.getLogger(__name__)

# ── Latest TG Desktop version (auto-fetched from GitHub) ─────────────
_latest_tdesktop_version: Optional[str] = None
_latest_tdesktop_checked_at: Optional[_dt] = None
_TDESKTOP_CHECK_INTERVAL = _td(hours=24)


async def fetch_latest_tdesktop_version() -> Optional[str]:
    """Fetch latest Telegram Desktop version from GitHub releases API."""
    global _latest_tdesktop_version, _latest_tdesktop_checked_at
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/repos/telegramdesktop/tdesktop/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 200:
                tag = resp.json().get("tag_name", "")
                version = tag.lstrip("v")
                if _re.match(r"\d+\.\d+(\.\d+)?", version):
                    _latest_tdesktop_version = version
                    _latest_tdesktop_checked_at = _dt.utcnow()
                    logger.info(f"Latest TG Desktop version: {version}")
                    return version
    except Exception as e:
        logger.warning(f"Failed to fetch latest TG Desktop version: {e}")
    return _latest_tdesktop_version


async def get_cached_tdesktop_version() -> Optional[str]:
    """Return cached version, refreshing if stale (>24h)."""
    if (
        _latest_tdesktop_version is None
        or _latest_tdesktop_checked_at is None
        or _dt.utcnow() - _latest_tdesktop_checked_at > _TDESKTOP_CHECK_INTERVAL
    ):
        return await fetch_latest_tdesktop_version()
    return _latest_tdesktop_version


from app.schemas.telegram_outreach import (
    TgProxyGroupCreate, TgProxyGroupUpdate, TgProxyGroupResponse,
    TgProxyCreate, TgProxyBulkCreate, TgProxyResponse,
    TgAccountTagCreate, TgAccountTagResponse,
    TgAccountCreate, TgAccountUpdate, TgAccountResponse, TgAccountListResponse,
    TgCampaignCreate, TgCampaignUpdate, TgCampaignResponse, TgCampaignListResponse,
    TgCampaignStatsResponse,
    TgRecipientResponse, TgRecipientListResponse,
    TgRecipientUploadText, TgRecipientUploadCSVMapping,
    TgCheckDuplicatesRequest, TgCheckDuplicatesResponse, TgDuplicateDetail, TgBulkRemoveRecipients,
    TgSequenceSchema, TgSequenceStepSchema, TgStepVariantSchema,
    TgSequencePreviewRequest, TgSequencePreviewResponse,
    TgOutreachMessageResponse, TgOutreachMessageListResponse,
    TgBulkAssignProxy, TgBulkTag, TgBulkAccountIds,
    TgTeleRaptorImportRequest, TgTeleRaptorImportResponse,
    TgBlacklistUploadText, TgBlacklistResponse, TgBlacklistListResponse,
    TgWarmupStatusResponse, TgWarmupLogResponse,
    TgWarmupChannelCreate, TgWarmupChannelResponse,
    TgCampaignTimelineResponse, TgTimelineRecipient, TgTimelineStep, TgTimelineStepStatus,
    TgCrmCustomFieldCreate, TgCrmCustomFieldUpdate, TgCrmCustomFieldResponse,
    TgCrmLeadFieldValueUpdate, TgCrmLeadFieldValueResponse,
)

router = APIRouter(prefix="/telegram-outreach", tags=["Telegram Outreach"])

# Official Telegram Desktop (tdesktop) credentials — using these makes the
# connection look like a legitimate Desktop client and avoids api_id ↔ fingerprint
# mismatch that Telegram uses to detect automation.
TDESKTOP_API_ID = 2040
TDESKTOP_API_HASH = "b18441a1ff607e10a989891a5462e627"


def _warmup_info(acc) -> dict:
    """Compute effective_daily_limit, warmup_day, is_young_session, and active warmup progress."""
    from app.services.sending_worker import get_effective_daily_limit, WARMUP_MSGS_PER_DAY, is_young_session as _is_young
    from datetime import datetime
    eff = get_effective_daily_limit(acc)
    day = None
    created = getattr(acc, "telegram_created_at", None) or acc.session_created_at
    if not getattr(acc, "skip_warmup", False) and created:
        age = (datetime.utcnow() - created).days
        base = acc.daily_message_limit or 10
        if WARMUP_MSGS_PER_DAY * (age + 1) < base:
            day = age + 1
    # Active warmup progress
    warmup_progress = None
    if getattr(acc, "warmup_active", False) and acc.warmup_started_at:
        wu_day = (datetime.utcnow() - acc.warmup_started_at).days + 1
        phase = "maintenance" if wu_day > 14 else "active"
        warmup_progress = {"day": wu_day, "total_days": 14, "phase": phase}
    return {
        "effective_daily_limit": eff, "warmup_day": day, "is_young_session": _is_young(acc),
        "warmup_active": getattr(acc, "warmup_active", False),
        "warmup_started_at": acc.warmup_started_at if hasattr(acc, "warmup_started_at") else None,
        "warmup_actions_done": getattr(acc, "warmup_actions_done", 0) or 0,
        "warmup_progress": warmup_progress,
    }


async def _extract_and_save_string_session(
    session_bytes: bytes,
    phone: str,
    api_id: int,
    api_hash: str,
    tg_account: "TgAccount",
    db: AsyncSession,
) -> Optional[str]:
    """Extract StringSession from .session bytes, save to TgAccount and TelegramDMAccount.

    Returns the string_session string on success, None on failure.
    This is best-effort: if extraction fails, the import still succeeds.
    """
    try:
        string_session, user_info = await session_file_to_string_session(
            session_bytes, api_id, api_hash
        )
    except Exception as e:
        logger.warning(f"StringSession extraction failed for {phone}: {e}")
        return None

    # Save to TgAccount
    tg_account.string_session = string_session

    # Determine user info: prefer live data from Telethon, fall back to TgAccount fields
    tg_user_id = None
    username = tg_account.username
    first_name = tg_account.first_name
    last_name = tg_account.last_name

    if user_info:
        tg_user_id = user_info.get("telegram_user_id")
        username = user_info.get("username") or username
        first_name = user_info.get("first_name") or first_name
        last_name = user_info.get("last_name") or last_name

        # Also update TgAccount with live data if it was missing
        if tg_user_id and not tg_account.telegram_user_id:
            tg_account.telegram_user_id = tg_user_id
        if user_info.get("username") and not tg_account.username:
            tg_account.username = user_info["username"]
        if user_info.get("first_name") and not tg_account.first_name:
            tg_account.first_name = user_info["first_name"]
        if user_info.get("last_name") and not tg_account.last_name:
            tg_account.last_name = user_info["last_name"]

    # Create or update TelegramDMAccount
    existing_dm = None
    if phone:
        result = await db.execute(
            select(TelegramDMAccount).where(TelegramDMAccount.phone == phone)
        )
        existing_dm = result.scalar()

    if existing_dm:
        existing_dm.string_session = string_session
        existing_dm.auth_status = "active"
        if tg_user_id:
            existing_dm.telegram_user_id = tg_user_id
        if username:
            existing_dm.username = username
        if first_name:
            existing_dm.first_name = first_name
        if last_name:
            existing_dm.last_name = last_name
        logger.info(f"Updated TelegramDMAccount for {phone} with StringSession")
    else:
        dm_account = TelegramDMAccount(
            phone=phone,
            telegram_user_id=tg_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            string_session=string_session,
            auth_status="active",
            company_id=1,
            is_connected=False,
        )
        db.add(dm_account)
        logger.info(f"Created TelegramDMAccount for {phone} with StringSession")

    return string_session


def _estimate_registration_date(tg_user_id: Optional[int]) -> Optional[str]:
    """Estimate Telegram account registration date from user_id.

    Telegram user IDs are roughly sequential. Known anchor points:
    - ID ~10M: ~2013-10
    - ID ~100M: ~2015-07
    - ID ~500M: ~2018-01
    - ID ~1B: ~2020-06
    - ID ~1.5B: ~2021-06
    - ID ~2B: ~2022-03
    - ID ~5B: ~2022-12
    - ID ~6B: ~2023-06
    - ID ~7B: ~2024-06
    - ID ~8B: ~2025-06
    """
    if not tg_user_id or tg_user_id <= 0:
        return None
    from datetime import datetime as dt
    anchors = [
        (10_000_000,    dt(2013, 10, 1)),
        (100_000_000,   dt(2015, 7, 1)),
        (500_000_000,   dt(2018, 1, 1)),
        (1_000_000_000, dt(2020, 6, 1)),
        (1_500_000_000, dt(2021, 6, 1)),
        (2_000_000_000, dt(2022, 3, 1)),
        (5_000_000_000, dt(2022, 12, 1)),
        (6_000_000_000, dt(2023, 6, 1)),
        (7_000_000_000, dt(2024, 6, 1)),
        (8_000_000_000, dt(2025, 6, 1)),
    ]
    uid = tg_user_id
    if uid <= anchors[0][0]:
        return anchors[0][1].isoformat()
    if uid >= anchors[-1][0]:
        return anchors[-1][1].isoformat()
    for i in range(len(anchors) - 1):
        id1, d1 = anchors[i]
        id2, d2 = anchors[i + 1]
        if id1 <= uid <= id2:
            ratio = (uid - id1) / (id2 - id1)
            est = dt.fromtimestamp(d1.timestamp() + ratio * (d2.timestamp() - d1.timestamp()))
            return est.isoformat()
    return None


def _parse_session_date(register_time: Optional[str], tgid: Optional[int] = None,
                        reg_date: Optional[float] = None):
    """Get session creation date from reg_date (unix ts), register_time string, or estimate from tgid."""
    from datetime import datetime as dt
    # Prefer reg_date unix timestamp (from TeleRaptor JSON)
    if reg_date:
        try:
            return dt.utcfromtimestamp(reg_date)
        except (ValueError, TypeError, OSError):
            pass
    if register_time:
        try:
            return dt.fromisoformat(register_time).replace(tzinfo=None)
        except (ValueError, TypeError):
            pass
    if tgid:
        est = _estimate_registration_date(tgid)
        if est:
            try:
                return dt.fromisoformat(est)
            except (ValueError, TypeError):
                pass
    return None


def _detect_country(phone: str) -> Optional[str]:
    """Detect country code from phone number using phonenumbers lib."""
    try:
        import phonenumbers
        p = phonenumbers.parse(f"+{phone.lstrip('+')}")
        return phonenumbers.region_code_for_number(p) or None
    except Exception:
        # Fallback: common prefixes
        ph = phone.lstrip('+')
        _PREFIX_MAP = [
            ('7', 'RU'), ('380', 'UA'), ('375', 'BY'), ('371', 'LV'), ('370', 'LT'), ('372', 'EE'),
            ('1', 'US'), ('44', 'GB'), ('49', 'DE'), ('33', 'FR'), ('34', 'ES'), ('39', 'IT'),
            ('351', 'PT'), ('55', 'BR'), ('90', 'TR'), ('91', 'IN'), ('86', 'CN'), ('81', 'JP'),
            ('82', 'KR'), ('971', 'AE'), ('966', 'SA'), ('48', 'PL'), ('31', 'NL'), ('46', 'SE'),
            ('47', 'NO'), ('45', 'DK'), ('358', 'FI'), ('41', 'CH'), ('43', 'AT'), ('36', 'HU'),
            ('420', 'CZ'), ('40', 'RO'), ('359', 'BG'), ('385', 'HR'), ('381', 'RS'),
            ('994', 'AZ'), ('995', 'GE'), ('374', 'AM'), ('998', 'UZ'), ('996', 'KG'), ('992', 'TJ'),
            ('993', 'TM'), ('7700', 'KZ'), ('77', 'KZ'),
        ]
        for prefix, code in sorted(_PREFIX_MAP, key=lambda x: -len(x[0])):
            if ph.startswith(prefix):
                return code
        return None


# ═══════════════════════════════════════════════════════════════════════
# PROXY HELPERS
# ═══════════════════════════════════════════════════════════════════════


async def _get_free_proxies(session: AsyncSession, proxy_group_id: int,
                            exclude_account_ids: list[int] | None = None) -> list[TgProxy]:
    """Get active proxies from a group not assigned to any active account."""
    assigned_q = (
        select(TgAccount.assigned_proxy_id)
        .where(
            TgAccount.assigned_proxy_id.isnot(None),
            TgAccount.status.in_([
                TgAccountStatus.ACTIVE, TgAccountStatus.PAUSED,
                TgAccountStatus.FROZEN, TgAccountStatus.SPAMBLOCKED,
            ]),
        )
    )
    if exclude_account_ids:
        assigned_q = assigned_q.where(~TgAccount.id.in_(exclude_account_ids))
    assigned_result = await session.execute(assigned_q)
    assigned_ids = {r[0] for r in assigned_result.all()}

    proxy_q = (
        select(TgProxy)
        .where(TgProxy.proxy_group_id == proxy_group_id, TgProxy.is_active == True)
    )
    if assigned_ids:
        proxy_q = proxy_q.where(~TgProxy.id.in_(assigned_ids))
    result = await session.execute(proxy_q.order_by(TgProxy.id))
    return list(result.scalars().all())


async def _try_reassign_proxy(session: AsyncSession, account: TgAccount) -> TgProxy | None:
    """Try to assign a free proxy from the account's proxy group. Returns proxy or None."""
    if not account.proxy_group_id:
        return None
    free = await _get_free_proxies(session, account.proxy_group_id,
                                   exclude_account_ids=[account.id])
    if free:
        account.assigned_proxy_id = free[0].id
        return free[0]
    return None


async def _resolve_dm_proxy(account: TelegramDMAccount, session: AsyncSession) -> dict | None:
    """Resolve proxy_config for DM account. Falls back to TgAccount.assigned_proxy if NULL."""
    if account.proxy_config:
        return account.proxy_config
    if not account.phone:
        return None
    tg_result = await session.execute(
        select(TgProxy).join(TgAccount, TgAccount.assigned_proxy_id == TgProxy.id)
        .where(TgAccount.phone == account.phone, TgProxy.is_active.is_(True)).limit(1)
    )
    proxy = tg_result.scalar_one_or_none()
    if not proxy:
        logger.warning(f"Proxy fallback: dm_account {account.id} ({account.phone}) — no proxy found in TgAccount either")
        return None
    resolved = {
        "type": proxy.protocol.value if proxy.protocol else "socks5",
        "host": proxy.host,
        "port": proxy.port,
        "username": proxy.username,
        "password": proxy.password,
    }
    logger.info(f"Proxy fallback: dm_account {account.id} ({account.phone}) ← TgAccount proxy {proxy.host}:{proxy.port}")
    return resolved


async def _sync_proxy_to_dm_account(session: AsyncSession, phone: str, proxy: TgProxy | None):
    """Sync assigned proxy from TgAccount to TelegramDMAccount.proxy_config (matched by phone)."""
    if not phone:
        return
    result = await session.execute(
        select(TelegramDMAccount).where(TelegramDMAccount.phone == phone)
    )
    dm_acc = result.scalar_one_or_none()
    if not dm_acc:
        return
    if proxy:
        dm_acc.proxy_config = {
            "type": proxy.protocol.value if proxy.protocol else "socks5",
            "host": proxy.host,
            "port": proxy.port,
            "username": proxy.username,
            "password": proxy.password,
        }
    else:
        dm_acc.proxy_config = None
    logger.info(f"Proxy sync: dm_account {dm_acc.id} ({phone}) ← proxy {'%s:%s' % (proxy.host, proxy.port) if proxy else 'cleared'}")


# ═══════════════════════════════════════════════════════════════════════
# PROXY GROUPS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/proxy-groups", response_model=list[TgProxyGroupResponse])
async def list_proxy_groups(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgProxyGroup).order_by(TgProxyGroup.name)
    )
    groups = result.scalars().all()
    out = []
    for g in groups:
        proxies_count_q = await session.execute(
            select(func.count(TgProxy.id)).where(TgProxy.proxy_group_id == g.id)
        )
        out.append(TgProxyGroupResponse(
            id=g.id, name=g.name, country=g.country, description=g.description,
            proxies_count=proxies_count_q.scalar() or 0,
            created_at=g.created_at,
        ))
    return out


@router.post("/proxy-groups", response_model=TgProxyGroupResponse)
async def create_proxy_group(data: TgProxyGroupCreate, session: AsyncSession = Depends(get_session)):
    group = TgProxyGroup(name=data.name, country=data.country, description=data.description)
    session.add(group)
    await session.flush()
    return TgProxyGroupResponse(id=group.id, name=group.name, country=group.country,
                                 description=group.description, proxies_count=0, created_at=group.created_at)


@router.put("/proxy-groups/{group_id}", response_model=TgProxyGroupResponse)
async def update_proxy_group(group_id: int, data: TgProxyGroupUpdate, session: AsyncSession = Depends(get_session)):
    group = await session.get(TgProxyGroup, group_id)
    if not group:
        raise HTTPException(404, "Proxy group not found")
    if data.name is not None:
        group.name = data.name
    if data.country is not None:
        group.country = data.country
    if data.description is not None:
        group.description = data.description
    await session.flush()
    proxies_count_q = await session.execute(
        select(func.count(TgProxy.id)).where(TgProxy.proxy_group_id == group.id)
    )
    return TgProxyGroupResponse(id=group.id, name=group.name, country=group.country,
                                 description=group.description,
                                 proxies_count=proxies_count_q.scalar() or 0,
                                 created_at=group.created_at)


@router.delete("/proxy-groups/{group_id}")
async def delete_proxy_group(group_id: int, session: AsyncSession = Depends(get_session)):
    group = await session.get(TgProxyGroup, group_id)
    if not group:
        raise HTTPException(404, "Proxy group not found")
    await session.delete(group)
    return {"ok": True}


# ── Proxies within a group ─────────────────────────────────────────────

@router.get("/proxy-groups/{group_id}/proxies", response_model=list[TgProxyResponse])
async def list_proxies(group_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgProxy).where(TgProxy.proxy_group_id == group_id).order_by(TgProxy.id)
    )
    return [TgProxyResponse.model_validate(p) for p in result.scalars().all()]


@router.post("/proxy-groups/{group_id}/proxies", response_model=list[TgProxyResponse])
async def add_proxies_bulk(group_id: int, data: TgProxyBulkCreate, session: AsyncSession = Depends(get_session)):
    """Parse proxies from raw text and add to group."""
    group = await session.get(TgProxyGroup, group_id)
    if not group:
        raise HTTPException(404, "Proxy group not found")

    created = []
    for line in data.raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        proxy = _parse_proxy_line(line, data.protocol)
        if proxy:
            obj = TgProxy(proxy_group_id=group_id, **proxy)
            session.add(obj)
            created.append(obj)

    await session.flush()
    return [TgProxyResponse.model_validate(p) for p in created]


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(proxy_id: int, session: AsyncSession = Depends(get_session)):
    proxy = await session.get(TgProxy, proxy_id)
    if not proxy:
        raise HTTPException(404, "Proxy not found")
    await session.delete(proxy)
    return {"ok": True}


async def _check_single_proxy(proxy) -> dict:
    """Check a single proxy by connecting through it. Returns {alive, latency_ms, error}."""
    import asyncio
    import time

    host = proxy.host
    port = proxy.port
    protocol = proxy.protocol.value if hasattr(proxy.protocol, 'value') else proxy.protocol
    username = proxy.username
    password = proxy.password

    start = time.monotonic()

    try:
        if protocol in ("http", "https"):
            # HTTP CONNECT check — try to reach httpbin or telegram
            import aiohttp
            proxy_url = f"http://{host}:{port}"
            proxy_auth = aiohttp.BasicAuth(username, password) if username else None
            async with aiohttp.ClientSession() as cs:
                async with cs.get(
                    "http://httpbin.org/ip",
                    proxy=proxy_url,
                    proxy_auth=proxy_auth,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        latency = round((time.monotonic() - start) * 1000)
                        return {"alive": True, "latency_ms": latency, "error": None}
                    else:
                        return {"alive": False, "latency_ms": None, "error": f"HTTP {resp.status}"}

        elif protocol == "socks5":
            # SOCKS5 — TCP connect through proxy
            import socks
            import socket

            def _socks_check():
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, host, port, username=username, password=password)
                s.settimeout(15)
                s.connect(("149.154.167.50", 443))  # Telegram DC IP
                s.close()

            await asyncio.to_thread(_socks_check)
            latency = round((time.monotonic() - start) * 1000)
            return {"alive": True, "latency_ms": latency, "error": None}

        else:
            # MTProto or unknown — just TCP connect to proxy host:port
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10,
            )
            writer.close()
            await writer.wait_closed()
            latency = round((time.monotonic() - start) * 1000)
            return {"alive": True, "latency_ms": latency, "error": None}

    except asyncio.TimeoutError:
        return {"alive": False, "latency_ms": None, "error": "Timeout"}
    except Exception as e:
        return {"alive": False, "latency_ms": None, "error": str(e)[:100]}


@router.post("/proxies/{proxy_id}/check")
async def check_single_proxy(proxy_id: int, session: AsyncSession = Depends(get_session)):
    """Check if a single proxy is alive."""
    proxy = await session.get(TgProxy, proxy_id)
    if not proxy:
        raise HTTPException(404, "Proxy not found")

    result = await _check_single_proxy(proxy)
    proxy.is_active = result["alive"]
    proxy.last_checked_at = func.now()
    return {"proxy_id": proxy_id, **result}


@router.post("/proxy-groups/{group_id}/check")
async def check_proxy_group(group_id: int, auto_delete: bool = Query(False),
                             session: AsyncSession = Depends(get_session)):
    """Check all proxies in a group. If auto_delete=true, remove dead proxies."""
    group = await session.get(TgProxyGroup, group_id)
    if not group:
        raise HTTPException(404, "Proxy group not found")

    result = await session.execute(
        select(TgProxy).where(TgProxy.proxy_group_id == group_id).order_by(TgProxy.id)
    )
    proxies = list(result.scalars().all())

    results = []
    alive_count = 0
    dead_count = 0
    deleted_ids = []
    reassign_accounts = []

    for proxy in proxies:
        check = await _check_single_proxy(proxy)
        proxy.is_active = check["alive"]
        proxy.last_checked_at = func.now()

        if check["alive"]:
            alive_count += 1
        else:
            dead_count += 1
            # Reassign accounts that had this dead proxy
            affected = await session.execute(
                select(TgAccount).where(TgAccount.assigned_proxy_id == proxy.id)
            )
            for acc in affected.scalars().all():
                acc.assigned_proxy_id = None  # cleared now, reassigned below
                reassign_accounts.append(acc)
            if auto_delete:
                deleted_ids.append(proxy.id)
                await session.delete(proxy)

        results.append({
            "proxy_id": proxy.id,
            "host": proxy.host,
            "port": proxy.port,
            **check,
        })

    # Reassign accounts that lost their proxy to a free one from the same group
    reassigned_count = 0
    for acc in reassign_accounts:
        new_proxy = await _try_reassign_proxy(session, acc)
        await _sync_proxy_to_dm_account(session, acc.phone, new_proxy)
        if new_proxy:
            reassigned_count += 1

    return {
        "total": len(proxies),
        "alive": alive_count,
        "dead": dead_count,
        "deleted": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "reassigned": reassigned_count,
        "results": results,
    }


def _parse_proxy_line(line: str, protocol: str = "http") -> dict | None:
    """Parse proxy from formats: ip:port:user:pass or user:pass@ip:port or ip:port."""
    try:
        if "@" in line:
            creds, hostport = line.rsplit("@", 1)
            parts = creds.split(":", 1)
            hp = hostport.split(":", 1)
            return {"host": hp[0], "port": int(hp[1]), "username": parts[0],
                    "password": parts[1] if len(parts) > 1 else None, "protocol": protocol}
        parts = line.split(":")
        if len(parts) == 2:
            return {"host": parts[0], "port": int(parts[1]), "protocol": protocol}
        if len(parts) >= 4:
            return {"host": parts[0], "port": int(parts[1]),
                    "username": parts[2], "password": parts[3], "protocol": protocol}
        if len(parts) == 3:
            return {"host": parts[0], "port": int(parts[1]), "username": parts[2], "protocol": protocol}
    except (ValueError, IndexError):
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════
# ACCOUNT TAGS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/tags", response_model=list[TgAccountTagResponse])
async def list_tags(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(TgAccountTag).order_by(TgAccountTag.name))
    return [TgAccountTagResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/tags", response_model=TgAccountTagResponse)
async def create_tag(data: TgAccountTagCreate, session: AsyncSession = Depends(get_session)):
    tag = TgAccountTag(name=data.name, color=data.color)
    session.add(tag)
    await session.flush()
    return TgAccountTagResponse.model_validate(tag)


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, session: AsyncSession = Depends(get_session)):
    tag = await session.get(TgAccountTag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    await session.delete(tag)
    return {"ok": True}


@router.post("/accounts/bulk-tag")
async def bulk_tag_accounts(data: TgBulkTag, session: AsyncSession = Depends(get_session)):
    for aid in data.account_ids:
        existing = await session.execute(
            select(TgAccountTagLink).where(
                TgAccountTagLink.account_id == aid, TgAccountTagLink.tag_id == data.tag_id
            )
        )
        if not existing.scalar():
            session.add(TgAccountTagLink(account_id=aid, tag_id=data.tag_id))
    return {"ok": True, "count": len(data.account_ids)}


@router.post("/accounts/bulk-untag")
async def bulk_untag_accounts(data: TgBulkTag, session: AsyncSession = Depends(get_session)):
    for aid in data.account_ids:
        existing = await session.execute(
            select(TgAccountTagLink).where(
                TgAccountTagLink.account_id == aid, TgAccountTagLink.tag_id == data.tag_id
            )
        )
        link = existing.scalar()
        if link:
            await session.delete(link)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# ACCOUNTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/accounts", response_model=TgAccountListResponse)
async def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    tag_id: Optional[int] = None,
    proxy_group_id: Optional[int] = None,
    search: Optional[str] = None,
    project_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(TgAccount).options(
        selectinload(TgAccount.tags), selectinload(TgAccount.proxy_group),
        selectinload(TgAccount.assigned_proxy))
    count_query = select(func.count(TgAccount.id))

    # Filters
    if project_id is not None:
        query = query.where(TgAccount.project_id == project_id)
        count_query = count_query.where(TgAccount.project_id == project_id)
    if status:
        query = query.where(TgAccount.status == status)
        count_query = count_query.where(TgAccount.status == status)
    if proxy_group_id:
        query = query.where(TgAccount.proxy_group_id == proxy_group_id)
        count_query = count_query.where(TgAccount.proxy_group_id == proxy_group_id)
    if tag_id:
        query = query.join(TgAccountTagLink, TgAccountTagLink.account_id == TgAccount.id).where(
            TgAccountTagLink.tag_id == tag_id
        )
        count_query = count_query.join(TgAccountTagLink, TgAccountTagLink.account_id == TgAccount.id).where(
            TgAccountTagLink.tag_id == tag_id
        )
    if search:
        like = f"%{search}%"
        query = query.where(
            (TgAccount.phone.ilike(like)) | (TgAccount.username.ilike(like)) |
            (TgAccount.first_name.ilike(like)) | (TgAccount.last_name.ilike(like))
        )
        count_query = count_query.where(
            (TgAccount.phone.ilike(like)) | (TgAccount.username.ilike(like)) |
            (TgAccount.first_name.ilike(like)) | (TgAccount.last_name.ilike(like))
        )

    total = (await session.execute(count_query)).scalar() or 0

    query = query.order_by(desc(TgAccount.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    accounts = result.scalars().unique().all()

    # Backfill missing country_code and telegram_created_at (from tgid estimate)
    dirty = False
    for acc in accounts:
        if not acc.country_code and acc.phone:
            acc.country_code = _detect_country(acc.phone)
            if acc.country_code:
                dirty = True
        if acc.telegram_user_id:
            est = _parse_session_date(None, acc.telegram_user_id)
            if est:
                if not acc.telegram_created_at:
                    acc.telegram_created_at = est
                    dirty = True
                if not acc.session_created_at or (acc.session_created_at and est < acc.session_created_at):
                    acc.session_created_at = est
                    dirty = True
    if dirty:
        try:
            await session.commit()
        except Exception:
            await session.rollback()

    items = []
    for acc in accounts:
        # Count campaigns
        camp_count_q = await session.execute(
            select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.account_id == acc.id)
        )
        wu = _warmup_info(acc)
        items.append(TgAccountResponse(
            id=acc.id, phone=acc.phone, username=acc.username,
            first_name=acc.first_name, last_name=acc.last_name, bio=acc.bio,
            device_model=acc.device_model, system_version=acc.system_version,
            app_version=acc.app_version, lang_code=acc.lang_code,
            system_lang_code=acc.system_lang_code,
            status=acc.status.value if acc.status else "active",
            spamblock_type=acc.spamblock_type.value if acc.spamblock_type else "none",
            spamblock_end=getattr(acc, 'spamblock_end', None),
            daily_message_limit=acc.daily_message_limit,
            is_premium=acc.is_premium,
            effective_daily_limit=wu["effective_daily_limit"],
            warmup_day=wu["warmup_day"],
            is_young_session=wu["is_young_session"],
            skip_warmup=acc.skip_warmup,
            warmup_active=wu.get("warmup_active", False),
            warmup_started_at=wu.get("warmup_started_at"),
            warmup_actions_done=wu.get("warmup_actions_done", 0),
            warmup_progress=wu.get("warmup_progress"),
            messages_sent_today=acc.messages_sent_today,
            total_messages_sent=acc.total_messages_sent,
            proxy_group_id=acc.proxy_group_id,
            proxy_group_name=acc.proxy_group.name if acc.proxy_group else None,
            assigned_proxy_id=acc.assigned_proxy_id,
            assigned_proxy_host=f"{acc.assigned_proxy.host}:{acc.assigned_proxy.port}" if acc.assigned_proxy else None,
            tags=[TgAccountTagResponse.model_validate(t) for t in acc.tags],
            campaigns_count=camp_count_q.scalar() or 0,
            country_code=acc.country_code,
            telegram_created_at=getattr(acc, 'telegram_created_at', None),
            session_created_at=acc.session_created_at,
            last_connected_at=acc.last_connected_at,
            last_checked_at=acc.last_checked_at,
            created_at=acc.created_at, updated_at=acc.updated_at,
        ))

    return TgAccountListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/accounts", response_model=TgAccountResponse)
async def create_account(data: TgAccountCreate, session: AsyncSession = Depends(get_session)):
    # Check duplicate phone
    existing = await session.execute(select(TgAccount).where(TgAccount.phone == data.phone))
    if existing.scalar():
        raise HTTPException(409, f"Account with phone {data.phone} already exists")

    # Auto-generate unique fingerprint if not provided
    fp = _generate_random_fingerprint()
    is_premium = getattr(data, "is_premium", False)
    account = TgAccount(
        phone=data.phone, username=data.username,
        first_name=data.first_name, last_name=data.last_name, bio=data.bio,
        api_id=data.api_id, api_hash=data.api_hash,
        device_model=data.device_model or fp["device_model"],
        system_version=data.system_version or fp["system_version"],
        app_version=data.app_version or fp["app_version"],
        lang_code=data.lang_code or fp["lang_code"],
        system_lang_code=data.system_lang_code or fp["system_lang_code"],
        two_fa_password=data.two_fa_password,
        session_file=data.session_file_name,
        country_code=_detect_country(data.phone),
        session_created_at=func.now(),
        is_premium=is_premium,
        daily_message_limit=10 if is_premium else 5,
    )
    session.add(account)
    await session.flush()

    wu = _warmup_info(account)
    return TgAccountResponse(
        id=account.id, phone=account.phone, username=account.username,
        first_name=account.first_name, last_name=account.last_name, bio=account.bio,
        device_model=account.device_model, system_version=account.system_version,
        app_version=account.app_version, lang_code=account.lang_code,
        system_lang_code=account.system_lang_code,
        status="active", spamblock_type="none",
        daily_message_limit=account.daily_message_limit,
        is_premium=account.is_premium,
        effective_daily_limit=wu["effective_daily_limit"],
        warmup_day=wu["warmup_day"],
        skip_warmup=account.skip_warmup,
        warmup_active=wu.get("warmup_active", False),
        warmup_started_at=wu.get("warmup_started_at"),
        warmup_actions_done=wu.get("warmup_actions_done", 0),
        warmup_progress=wu.get("warmup_progress"),
        messages_sent_today=0, total_messages_sent=0,
        tags=[], campaigns_count=0,
        created_at=account.created_at, updated_at=account.updated_at,
    )


@router.put("/accounts/{account_id}", response_model=TgAccountResponse)
async def update_account(account_id: int, data: TgAccountUpdate, session: AsyncSession = Depends(get_session)):
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    changed_fields = data.model_dump(exclude_unset=True)
    for field, value in changed_fields.items():
        if field == "status" and value:
            setattr(account, field, TgAccountStatus(value))
        else:
            setattr(account, field, value)

    await session.flush()

    # Auto-sync proxy to DM account when assigned_proxy_id changes
    if "assigned_proxy_id" in changed_fields:
        proxy = await session.get(TgProxy, account.assigned_proxy_id) if account.assigned_proxy_id else None
        await _sync_proxy_to_dm_account(session, account.phone, proxy)

    # Auto-sync profile to Telegram if session exists and profile fields changed
    profile_fields = {"first_name", "last_name", "bio", "username"}
    changed_profile = profile_fields & set(changed_fields.keys())
    if changed_profile and account.api_id and account.api_hash and telegram_engine.session_file_exists(account.phone):
        try:
            kwargs = _account_connect_kwargs(account)
            await telegram_engine.connect(account_id, **kwargs)
            sync_params = {}
            if "first_name" in changed_profile:
                sync_params["first_name"] = account.first_name or ""
            if "last_name" in changed_profile:
                sync_params["last_name"] = account.last_name or ""
            if "bio" in changed_profile:
                sync_params["about"] = account.bio or ""
            if "username" in changed_profile:
                sync_params["username"] = account.username or ""
            if sync_params:
                await telegram_engine.update_profile(account_id, **sync_params)
            await telegram_engine.disconnect(account_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Auto-sync profile failed for {account.phone}: {e}")
    # Reload with relationships
    await session.refresh(account)
    result = await session.execute(
        select(TgAccount).where(TgAccount.id == account_id)
        .options(selectinload(TgAccount.tags), selectinload(TgAccount.proxy_group),
                 selectinload(TgAccount.assigned_proxy))
    )
    account = result.scalar_one()
    camp_count_q = await session.execute(
        select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.account_id == account.id)
    )
    wu = _warmup_info(account)
    return TgAccountResponse(
        id=account.id, phone=account.phone, username=account.username,
        first_name=account.first_name, last_name=account.last_name, bio=account.bio,
        device_model=account.device_model, system_version=account.system_version,
        app_version=account.app_version, lang_code=account.lang_code,
        system_lang_code=account.system_lang_code,
        status=account.status.value, spamblock_type=account.spamblock_type.value,
        daily_message_limit=account.daily_message_limit,
        is_premium=account.is_premium,
        effective_daily_limit=wu["effective_daily_limit"],
        warmup_day=wu["warmup_day"],
        skip_warmup=account.skip_warmup,
        warmup_active=wu.get("warmup_active", False),
        warmup_started_at=wu.get("warmup_started_at"),
        warmup_actions_done=wu.get("warmup_actions_done", 0),
        warmup_progress=wu.get("warmup_progress"),
        messages_sent_today=account.messages_sent_today,
        total_messages_sent=account.total_messages_sent,
        proxy_group_id=account.proxy_group_id,
        proxy_group_name=account.proxy_group.name if account.proxy_group else None,
        assigned_proxy_id=account.assigned_proxy_id,
        assigned_proxy_host=f"{account.assigned_proxy.host}:{account.assigned_proxy.port}" if account.assigned_proxy else None,
        tags=[TgAccountTagResponse.model_validate(t) for t in account.tags],
        campaigns_count=camp_count_q.scalar() or 0,
        last_connected_at=account.last_connected_at,
        last_checked_at=account.last_checked_at,
        created_at=account.created_at, updated_at=account.updated_at,
    )


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, session: AsyncSession = Depends(get_session)):
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    await session.delete(account)
    return {"ok": True}


@router.patch("/accounts/{account_id}/limit")
async def update_account_limit(account_id: int, daily_message_limit: int = Query(..., ge=1),
                                session: AsyncSession = Depends(get_session)):
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    account.daily_message_limit = daily_message_limit
    return {"ok": True, "daily_message_limit": daily_message_limit}


@router.post("/accounts/bulk-assign-proxy")
async def bulk_assign_proxy(data: TgBulkAssignProxy, session: AsyncSession = Depends(get_session)):
    """Assign proxy group AND auto-assign individual proxies 1:1."""
    free_proxies = await _get_free_proxies(session, data.proxy_group_id,
                                           exclude_account_ids=data.account_ids)
    proxy_iter = iter(free_proxies)
    assigned_count = 0
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.proxy_group_id = data.proxy_group_id
            proxy = next(proxy_iter, None)
            if proxy:
                account.assigned_proxy_id = proxy.id
                await _sync_proxy_to_dm_account(session, account.phone, proxy)
                assigned_count += 1
            else:
                account.assigned_proxy_id = None
                await _sync_proxy_to_dm_account(session, account.phone, None)
    return {"ok": True, "count": len(data.account_ids),
            "proxies_assigned": assigned_count,
            "proxies_available": len(free_proxies)}


@router.post("/accounts/bulk-set-limit")
async def bulk_set_limit(data: TgBulkAccountIds, daily_message_limit: int = Query(..., ge=1),
                          session: AsyncSession = Depends(get_session)):
    """Set daily message limit for multiple accounts."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.daily_message_limit = daily_message_limit
    return {"ok": True, "count": len(data.account_ids), "daily_message_limit": daily_message_limit}


@router.post("/accounts/bulk-skip-warmup")
async def bulk_skip_warmup(data: TgBulkAccountIds, skip: bool = Query(True),
                            session: AsyncSession = Depends(get_session)):
    """Toggle skip_warmup for multiple accounts."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.skip_warmup = skip
    return {"ok": True, "count": len(data.account_ids), "skip_warmup": skip}


# ── Active Warm-up endpoints ─────────────────────────────────────────

@router.post("/accounts/{account_id}/warmup/start")
async def warmup_start(account_id: int, session: AsyncSession = Depends(get_session)):
    """Start active warm-up for an account (14-day program)."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    if account.warmup_active:
        return {"ok": True, "message": "Warm-up already active"}
    account.warmup_active = True
    account.warmup_started_at = _dt.utcnow()
    account.warmup_actions_done = 0
    return {"ok": True, "message": "Warm-up started"}


@router.post("/accounts/{account_id}/warmup/stop")
async def warmup_stop(account_id: int, session: AsyncSession = Depends(get_session)):
    """Stop active warm-up for an account."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    account.warmup_active = False
    return {"ok": True, "message": "Warm-up stopped"}


@router.get("/accounts/{account_id}/warmup/status", response_model=TgWarmupStatusResponse)
async def warmup_status(account_id: int, session: AsyncSession = Depends(get_session)):
    """Get warm-up status and recent actions for an account."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    warmup_day = None
    if account.warmup_active and account.warmup_started_at:
        warmup_day = (_dt.utcnow() - account.warmup_started_at).days + 1

    # Count today's actions
    today_start = _dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = await session.execute(
        select(func.count(TgWarmupLog.id)).where(
            TgWarmupLog.account_id == account_id,
            TgWarmupLog.performed_at >= today_start,
        )
    )
    actions_today = today_q.scalar() or 0

    # Recent actions (last 20)
    recent_q = await session.execute(
        select(TgWarmupLog).where(
            TgWarmupLog.account_id == account_id,
        ).order_by(desc(TgWarmupLog.performed_at)).limit(20)
    )
    recent = recent_q.scalars().all()

    return TgWarmupStatusResponse(
        account_id=account_id,
        warmup_active=account.warmup_active,
        warmup_day=warmup_day,
        warmup_started_at=account.warmup_started_at,
        actions_done=account.warmup_actions_done or 0,
        actions_today=actions_today,
        recent_actions=[
            {
                "action_type": a.action_type.value if hasattr(a.action_type, 'value') else a.action_type,
                "detail": a.detail,
                "success": a.success,
                "performed_at": a.performed_at.isoformat() if a.performed_at else None,
            }
            for a in recent
        ],
    )


@router.get("/accounts/{account_id}/warmup/logs")
async def warmup_logs(account_id: int, session: AsyncSession = Depends(get_session)):
    """Get full warmup action history for debug modal."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    q = await session.execute(
        select(TgWarmupLog).where(
            TgWarmupLog.account_id == account_id,
        ).order_by(desc(TgWarmupLog.performed_at)).limit(200)
    )
    logs = q.scalars().all()
    return [
        {
            "action_type": a.action_type.value if hasattr(a.action_type, 'value') else a.action_type,
            "detail": a.detail,
            "success": a.success,
            "error_message": a.error_message,
            "performed_at": a.performed_at.isoformat() if a.performed_at else None,
        }
        for a in logs
    ]


@router.post("/accounts/bulk-warmup")
async def bulk_warmup(data: TgBulkAccountIds, action: str = Query("start"),
                       session: AsyncSession = Depends(get_session)):
    """Start or stop active warm-up for multiple accounts."""
    count = 0
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        if action == "start" and not account.warmup_active:
            account.warmup_active = True
            account.warmup_started_at = _dt.utcnow()
            account.warmup_actions_done = 0
            count += 1
        elif action == "stop" and account.warmup_active:
            account.warmup_active = False
            count += 1
    return {"ok": True, "count": count, "action": action}


# ── Warm-up Channels CRUD ───────────────────────────────────────────

DEFAULT_WARMUP_CHANNELS_SEED = [
    ("sokolov_outreach", "Sokolov Outreach"),
    ("dark_ads_chat", "Dark Ads Chat"),
    ("chatdnative", "Chat D Native"),
    ("cpa_lenta", "CPA Лента"),
    ("+-d8UvrddIvI1NWVi", None),
    ("leadssulive", "Leads Su Live"),
    ("+dNk09qoykgEzNWVi", None),
    ("thepartnerkin", "The Partnerkin"),
]


@router.get("/warmup/channels", response_model=list[TgWarmupChannelResponse])
async def list_warmup_channels(session: AsyncSession = Depends(get_session)):
    """List all curated warm-up channels."""
    result = await session.execute(
        select(TgWarmupChannel).order_by(TgWarmupChannel.id)
    )
    return result.scalars().all()


@router.post("/warmup/channels", response_model=TgWarmupChannelResponse, status_code=201)
async def add_warmup_channel(data: TgWarmupChannelCreate,
                              session: AsyncSession = Depends(get_session)):
    """Add a channel to the warm-up list."""
    url = data.url.strip()
    # Normalise: strip https://t.me/ prefix if given
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    ch = TgWarmupChannel(url=url, title=data.title)
    session.add(ch)
    await session.flush()
    await session.refresh(ch)
    return ch


@router.delete("/warmup/channels/{channel_id}")
async def delete_warmup_channel(channel_id: int,
                                 session: AsyncSession = Depends(get_session)):
    """Remove a channel from the warm-up list."""
    ch = await session.get(TgWarmupChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    await session.delete(ch)
    return {"ok": True}


@router.patch("/warmup/channels/{channel_id}", response_model=TgWarmupChannelResponse)
async def toggle_warmup_channel(channel_id: int, is_active: bool = Query(...),
                                 session: AsyncSession = Depends(get_session)):
    """Toggle a warm-up channel active/inactive."""
    ch = await session.get(TgWarmupChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    ch.is_active = is_active
    return ch


@router.post("/warmup/channels/seed")
async def seed_warmup_channels(session: AsyncSession = Depends(get_session)):
    """Seed default warm-up channels (idempotent)."""
    added = 0
    for url, title in DEFAULT_WARMUP_CHANNELS_SEED:
        existing = await session.execute(
            select(TgWarmupChannel).where(TgWarmupChannel.url == url)
        )
        if not existing.scalar_one_or_none():
            session.add(TgWarmupChannel(url=url, title=title))
            added += 1
    return {"ok": True, "added": added}


@router.post("/accounts/bulk-update-params")
async def bulk_update_params(
    data: TgBulkAccountIds,
    device_model: Optional[str] = Query(None),
    system_version: Optional[str] = Query(None),
    app_version: Optional[str] = Query(None),
    lang_code: Optional[str] = Query(None),
    system_lang_code: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Set tech params for multiple accounts."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        if device_model is not None:
            account.device_model = device_model
        if system_version is not None:
            account.system_version = system_version
        if app_version is not None:
            account.app_version = app_version
        if lang_code is not None:
            account.lang_code = lang_code
        if system_lang_code is not None:
            account.system_lang_code = system_lang_code
    return {"ok": True, "count": len(data.account_ids)}


# ── Device presets (from TeleRaptor) ──────────────────────────────────

DEVICE_PRESETS = [
    # Lenovo ThinkPad / IdeaPad / Legion
    "ThinkPadL13", "ThinkPadT590", "ThinkPadT480", "ThinkPadX1Carbon",
    "ThinkPadE14", "ThinkPadL14", "ThinkPadT14s", "ThinkPadX13",
    "IdeaPad5-15", "IdeaPad3-14", "81XH", "81UR", "82FG", "82HT",
    "LegionY540", "LegionY7000",
    # Dell
    "Latitude5401", "Latitude5520", "Latitude7420", "Precision3561",
    "Precision5560", "XPS13-9380", "XPS15-9510", "XPS17-9710",
    "Inspiron15-3511", "Inspiron14-5410", "Vostro3500", "DW0010", "DW1084",
    # HP
    "15t-ed002", "OmenX-17", "7DF52EA", "EliteBook840G8",
    "EliteBook850G7", "ProBook450G8", "ProBook445G7", "Pavilion15-eg",
    "ZBook15G7", "ZBookStudio-G8", "HP250G8", "HP255G7",
    # ASUS
    "S533EA", "X512JA", "VivoBookS15", "VivoBook15-X515",
    "ZenBook14-UX425", "ZenBook13-UX325", "ROG-Strix-G15",
    "TUF-Gaming-A15", "ExpertBook-B1", "C214MA",
    # Acer
    "A315-54K", "Aspire314", "Aspire5-A515", "AspireNitro5",
    "Swift3-SF314", "Swift5-SF514", "TravelMate-P2", "ConceptD3",
    # MSI
    "A11SCS", "GF63Thin", "GS66Stealth", "Modern14-B11",
    "Prestige14-A11", "Summit-E15", "Bravo15-B5",
    # Razer
    "RZ09-0281CE53", "RZ09-0367", "RZ09-0410", "RZ09-0370",
    # Samsung / LG
    "NP930X2K", "NP950XDB", "Galaxy-Book-Pro", "15Z980", "Gram17-17Z90P",
    # Apple (Telegram Desktop on macOS)
    "MacBookPro16,1", "MacBookPro17,1", "MacBookAir10,1",
    "MacBookPro14,3", "Macmini9,1", "iMac21,1",
    # Misc / FHD models
    "FHD-G15", "13-aw2000", "R7-3700U", "SurfacePro7", "SurfaceLaptop4",
    "SurfaceBook3", "Chromebook-Spin513",
]
SYSTEM_VERSIONS = [
    "Windows 10", "Windows 11",
    "macOS 12.6", "macOS 13.4", "macOS 14.2",
    "Ubuntu 22.04", "Fedora 38",
]
APP_VERSIONS = [
    "5.1.5 x64", "5.2.3 x64", "5.3.1 x64",
    "5.4.0 x64", "5.5.3 x64", "5.6.2 x64",
    "6.0.0 x64", "6.1.3 x64", "6.2.4 x64",
    "6.3.0 x64", "6.4.1 x64", "6.5.1 x64", "6.6.2 x64",
    "6.7.1 x64",
]
LANG_PRESETS = ["en", "pt", "es", "de", "fr", "it", "nl", "ru", "pl", "tr", "uk", "cs", "sv", "da", "fi"]
SYSTEM_LANG_PRESETS = [
    "en-US", "en-GB", "pt-PT", "pt-BR", "es-ES", "de-DE", "fr-FR",
    "it-IT", "nl-NL", "ru-RU", "pl-PL", "tr-TR", "uk-UA",
    "cs-CZ", "sv-SE", "da-DK", "fi-FI",
]


def _generate_random_fingerprint() -> dict:
    """Generate a random, realistic device fingerprint for a Telegram account.

    Each account gets a unique combination of device model, OS, app version,
    and language to avoid mass-detection by Telegram anti-spam systems.
    """
    import random
    return {
        "device_model": random.choice(DEVICE_PRESETS),
        "system_version": random.choice(SYSTEM_VERSIONS),
        "app_version": random.choice(APP_VERSIONS),
        "lang_code": random.choice(LANG_PRESETS),
        "system_lang_code": random.choice(SYSTEM_LANG_PRESETS),
    }


@router.post("/accounts/bulk-randomize-device")
async def bulk_randomize_device(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Randomize full device fingerprint (model, OS, app version, language) for selected accounts."""
    updated = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        fp = _generate_random_fingerprint()
        account.device_model = fp["device_model"]
        account.system_version = fp["system_version"]
        account.app_version = fp["app_version"]
        account.lang_code = fp["lang_code"]
        account.system_lang_code = fp["system_lang_code"]
        updated.append({"id": aid, **fp})
    return {"ok": True, "count": len(updated), "updated": updated}


@router.post("/accounts/bulk-switch-to-tdesktop")
async def bulk_switch_to_tdesktop(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Switch selected accounts to official Telegram Desktop api_id/api_hash.

    This ensures fingerprint ↔ api_id consistency: the Desktop-style device
    fingerprints (PC models, Windows, app version "x.x.x x64") match the
    official tdesktop api_id, preventing Telegram from detecting automation.

    WARNING: Accounts must be re-authorized after switching api_id (new session required).
    """
    switched = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        old_api_id = account.api_id
        account.api_id = TDESKTOP_API_ID
        account.api_hash = TDESKTOP_API_HASH
        switched.append({"id": aid, "phone": account.phone,
                         "old_api_id": old_api_id, "new_api_id": TDESKTOP_API_ID})
    return {
        "ok": True,
        "count": len(switched),
        "switched": switched,
        "note": "Accounts must be re-authorized (new session) after switching api_id.",
    }


# Known default fingerprints that indicate no randomization was applied
_DEFAULT_FINGERPRINTS = {"PC 64bit", "Samsung SM-G998B"}


@router.post("/accounts/migrate-fingerprints")
async def migrate_default_fingerprints(session: AsyncSession = Depends(get_session)):
    """One-time migration: randomize fingerprints for all accounts that still have shared defaults."""
    result = await session.execute(
        select(TgAccount).where(
            TgAccount.device_model.in_(list(_DEFAULT_FINGERPRINTS))
        )
    )
    accounts = result.scalars().all()
    updated = []
    for acc in accounts:
        fp = _generate_random_fingerprint()
        acc.device_model = fp["device_model"]
        acc.system_version = fp["system_version"]
        acc.app_version = fp["app_version"]
        acc.lang_code = fp["lang_code"]
        acc.system_lang_code = fp["system_lang_code"]
        updated.append(acc.id)
    return {"ok": True, "migrated": len(updated), "account_ids": updated}


@router.get("/accounts/device-presets")
async def get_device_presets():
    """Return available device presets for UI."""
    return {
        "devices": DEVICE_PRESETS,
        "system_versions": SYSTEM_VERSIONS,
        "app_versions": APP_VERSIONS,
        "lang_codes": LANG_PRESETS,
        "system_lang_codes": SYSTEM_LANG_PRESETS,
    }


@router.get("/app-version/latest")
async def get_latest_app_version():
    """Return the latest known TG Desktop version (auto-fetched from GitHub)."""
    version = await get_cached_tdesktop_version()
    return {
        "latest_version": f"{version} x64" if version else None,
        "raw_version": version,
        "checked_at": _latest_tdesktop_checked_at.isoformat() if _latest_tdesktop_checked_at else None,
        "current_presets": APP_VERSIONS,
    }


@router.post("/app-version/refresh")
async def refresh_app_version():
    """Force re-fetch the latest TG Desktop version from GitHub."""
    global _latest_tdesktop_checked_at
    _latest_tdesktop_checked_at = None  # force refresh
    version = await fetch_latest_tdesktop_version()
    return {
        "latest_version": f"{version} x64" if version else None,
        "raw_version": version,
    }


@router.post("/accounts/bulk-update-app-version")
async def bulk_update_app_version(
    data: TgBulkAccountIds = None,
    version: Optional[str] = Query(None, description="Specific version string to set (e.g. '6.7.1 x64')"),
    all_accounts: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Update app_version for selected or all accounts to the latest (or specified) version."""
    if version:
        target_version = version
    else:
        latest = await get_cached_tdesktop_version()
        if not latest:
            raise HTTPException(400, "Could not fetch latest version. Provide version= manually.")
        target_version = f"{latest} x64"

    if all_accounts:
        result = await session.execute(select(TgAccount))
        accounts = result.scalars().all()
    elif data and data.account_ids:
        accounts = []
        for aid in data.account_ids:
            acc = await session.get(TgAccount, aid)
            if acc:
                accounts.append(acc)
    else:
        raise HTTPException(400, "Provide account_ids or set all_accounts=true")

    for acc in accounts:
        acc.app_version = target_version
    await session.commit()

    return {"ok": True, "version": target_version, "updated": len(accounts)}


@router.post("/accounts/bulk-check")
async def bulk_check_accounts(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Redirect to bulk-check-live."""
    return await bulk_check_live(data, session)


# ── Name presets by category ───────────────────────────────────────────

NAME_PRESETS = {
    "male_pt": {
        "first": ["João","Pedro","Miguel","Tiago","Francisco","Diogo","Gonçalo","André","José","António","Manuel","Afonso","Tomás","Rodrigo","Guilherme","Bernardo","David","Eduardo","Filipe","Gabriel","Henrique","Rui","Nuno","Luís","Vasco","Rafael","Ricardo","Jorge","Carlos","Paulo","Bruno","Fernando","Daniel","Samuel"],
        "last": ["Silva","Santos","Ferreira","Pereira","Oliveira","Costa","Rodrigues","Martins","Sousa","Fernandes","Gonçalves","Gomes","Lopes","Marques","Alves","Almeida","Ribeiro","Pinto","Carvalho","Teixeira","Moreira","Correia","Mendes","Nunes","Soares","Vieira","Monteiro","Cardoso","Rocha","Neves"],
    },
    "female_pt": {
        "first": ["Maria","Ana","Sofia","Beatriz","Inês","Mariana","Carolina","Leonor","Matilde","Catarina","Francisca","Rita","Joana","Sara","Marta","Laura","Diana","Lara","Eva","Clara","Raquel","Daniela","Filipa","Patrícia","Helena","Teresa","Isabel","Cláudia","Andreia","Carla"],
        "last": ["Silva","Santos","Ferreira","Pereira","Oliveira","Costa","Rodrigues","Martins","Sousa","Fernandes","Gonçalves","Gomes","Lopes","Marques","Alves","Almeida","Ribeiro","Pinto","Carvalho","Teixeira","Moreira","Correia","Mendes","Nunes","Soares","Vieira","Monteiro","Cardoso","Rocha","Neves"],
    },
    "male_en": {
        "first": ["James","John","Robert","Michael","William","David","Richard","Joseph","Thomas","Christopher","Daniel","Matthew","Anthony","Mark","Steven","Andrew","Paul","Joshua","Kenneth","Kevin","Brian","George","Timothy","Ronald","Edward","Jason","Jeffrey","Ryan","Jacob","Gary"],
        "last": ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Anderson","Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Harris","Clark","Lewis","Robinson","Walker","Young","Allen","King","Wright","Scott","Hill"],
    },
    "female_en": {
        "first": ["Mary","Patricia","Jennifer","Linda","Barbara","Elizabeth","Susan","Jessica","Sarah","Karen","Lisa","Nancy","Betty","Margaret","Sandra","Ashley","Emily","Donna","Michelle","Carol","Amanda","Melissa","Deborah","Stephanie","Rebecca","Sharon","Laura","Cynthia","Kathleen","Amy"],
        "last": ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Anderson","Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Harris","Clark","Lewis","Robinson","Walker","Young","Allen","King","Wright","Scott","Hill"],
    },
    "male_ru": {
        "first": ["Александр","Дмитрий","Максим","Иван","Артём","Михаил","Даниил","Кирилл","Андрей","Никита","Егор","Илья","Алексей","Роман","Владимир","Сергей","Павел","Николай","Денис","Антон","Виктор","Олег","Евгений","Игорь","Константин","Юрий","Борис","Василий","Григорий","Тимофей"],
        "last": ["Иванов","Смирнов","Кузнецов","Попов","Васильев","Петров","Соколов","Михайлов","Новиков","Фёдоров","Морозов","Волков","Алексеев","Лебедев","Семёнов","Егоров","Павлов","Козлов","Степанов","Николаев","Орлов","Андреев","Макаров","Никитин","Захаров","Зайцев","Соловьёв","Борисов","Яковлев","Григорьев"],
    },
    "female_ru": {
        "first": ["Анна","Мария","Елена","Ольга","Наталья","Екатерина","Татьяна","Ирина","Светлана","Марина","Юлия","Дарья","Алина","Виктория","Полина","Анастасия","Валерия","Кристина","София","Александра","Вера","Людмила","Оксана","Галина","Лариса","Надежда","Евгения","Диана","Яна","Карина"],
        "last": ["Иванова","Смирнова","Кузнецова","Попова","Васильева","Петрова","Соколова","Михайлова","Новикова","Фёдорова","Морозова","Волкова","Алексеева","Лебедева","Семёнова","Егорова","Павлова","Козлова","Степанова","Николаева","Орлова","Андреева","Макарова","Никитина","Захарова","Зайцева","Борисова","Яковлева","Григорьева","Романова"],
    },
}


def _generate_username(first: str, last: str) -> str:
    """Generate username from name+surname like TeleRaptor."""
    import random, re
    f = re.sub(r'[^a-zA-Z0-9]', '', first.lower().encode('ascii', 'ignore').decode())
    l = re.sub(r'[^a-zA-Z0-9]', '', last.lower().encode('ascii', 'ignore').decode())
    if not f:
        f = "user"
    if not l:
        l = "acc"
    num = random.randint(1, 99)
    patterns = [
        f"{f}{l}{num}", f"{f}_{l}", f"{f}.{l}{num}", f"{f}{l[0]}{num}",
        f"{l}{f[0]}{num}", f"{f}{num}{l[0]}", f"{f[0]}{l}{num}",
    ]
    return random.choice(patterns)


# ══════════════════════════════════════════════════════════════════════
# Staggered bulk operations — profile-changing ops with 30-120s delays
# ══════════════════════════════════════════════════════════════════════

import asyncio as _asyncio
import uuid as _uuid

_bulk_op_progress: dict[str, dict] = {}
_STAGGER_MIN = 30   # seconds
_STAGGER_MAX = 120  # seconds


def _create_bulk_task(total: int, operation: str) -> str:
    """Create a progress entry and return task_id."""
    task_id = _uuid.uuid4().hex[:12]
    _bulk_op_progress[task_id] = {
        "task_id": task_id,
        "status": "running",
        "operation": operation,
        "total": total,
        "completed": 0,
        "synced": 0,
        "skipped": 0,
        "errors": [],
        "current_phone": None,
        "next_delay": 0,
        "started_at": _dt.utcnow().isoformat(),
    }
    return task_id


async def _staggered_profile_sync(task_id: str, account_ids: list[int]):
    """Background: sync profile (name/bio/username) to Telegram with staggered delays."""
    import random
    from app.db import async_session_maker

    progress = _bulk_op_progress[task_id]
    try:
        async with async_session_maker() as session:
            for i, aid in enumerate(account_ids):
                account = await session.get(TgAccount, aid)
                if not account or not account.api_id or not account.api_hash:
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue
                if not telegram_engine.session_file_exists(account.phone):
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                progress["current_phone"] = account.phone
                try:
                    kwargs = _account_connect_kwargs(account)
                    await telegram_engine.connect(aid, **kwargs)
                    await telegram_engine.update_profile(
                        aid,
                        first_name=account.first_name or "",
                        last_name=account.last_name or "",
                        about=account.bio or "",
                        username=account.username or None,
                    )
                    await telegram_engine.disconnect(aid)
                    progress["synced"] += 1
                except Exception as e:
                    progress["errors"].append(f"{account.phone}: {str(e)[:80]}")
                    logger.warning(f"[STAGGERED] sync failed for {account.phone}: {e}")

                progress["completed"] += 1

                # Staggered delay between accounts
                if i < len(account_ids) - 1:
                    delay = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
                    progress["next_delay"] = round(delay)
                    await _asyncio.sleep(delay)
                    progress["next_delay"] = 0
    except Exception as e:
        logger.error(f"[STAGGERED] task {task_id} crashed: {e}")
        progress["errors"].append(f"Task error: {str(e)[:120]}")
    finally:
        progress["status"] = "completed"
        progress["current_phone"] = None
        progress["next_delay"] = 0


async def _staggered_photo_upload(task_id: str, account_ids: list[int], photo_map: dict[int, str]):
    """Background: upload profile photos to Telegram with staggered delays."""
    import random
    from app.db import async_session_maker
    from telethon.tl.functions.photos import GetUserPhotosRequest, DeletePhotosRequest, UploadProfilePhotoRequest
    from telethon.tl.types import InputPhoto, InputUserSelf

    progress = _bulk_op_progress[task_id]
    try:
        async with async_session_maker() as session:
            for i, aid in enumerate(account_ids):
                account = await session.get(TgAccount, aid)
                photo_path = photo_map.get(aid)
                if not account or not photo_path:
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue
                if not account.api_id or not account.api_hash or not telegram_engine.session_file_exists(account.phone):
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                progress["current_phone"] = account.phone
                try:
                    proxy = None
                    if account.assigned_proxy_id:
                        _p_rec = await session.get(TgProxy, account.assigned_proxy_id)
                        if _p_rec:
                            proxy = {"host": _p_rec.host, "port": _p_rec.port, "username": _p_rec.username,
                                     "password": _p_rec.password, "protocol": _p_rec.protocol.value if hasattr(_p_rec.protocol, 'value') else _p_rec.protocol}
                    kwargs = _account_connect_kwargs(account, proxy)
                    try:
                        await telegram_engine.disconnect(aid)
                    except Exception:
                        pass
                    # Try with proxy first; fall back to direct if proxy fails
                    try:
                        _client = await telegram_engine.connect(aid, **kwargs)
                    except Exception as conn_err:
                        logger.warning(f"[STAGGERED] {account.phone} proxy connect failed: {conn_err}, retrying direct")
                        try:
                            await telegram_engine.disconnect(aid)
                        except Exception:
                            pass
                        kwargs_direct = _account_connect_kwargs(account, None)
                        _client = await telegram_engine.connect(aid, **kwargs_direct)
                    if await _client.is_user_authorized():
                        me_user = InputUserSelf()
                        # Delete old photos
                        try:
                            _photos = await _client(GetUserPhotosRequest(user_id=me_user, offset=0, max_id=0, limit=100))
                            if hasattr(_photos, 'photos'):
                                for old_p in _photos.photos:
                                    try:
                                        await _client(DeletePhotosRequest(id=[InputPhoto(id=old_p.id, access_hash=old_p.access_hash, file_reference=old_p.file_reference)]))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        # Upload new photo
                        uploaded = await _client.upload_file(photo_path)
                        await _client(UploadProfilePhotoRequest(file=uploaded))
                        progress["synced"] += 1
                    await telegram_engine.disconnect(aid)
                except Exception as e:
                    progress["errors"].append(f"{account.phone}: {str(e)[:80]}")
                    logger.warning(f"[STAGGERED] photo upload failed for {account.phone}: {e}")

                progress["completed"] += 1

                if i < len(account_ids) - 1:
                    delay = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
                    progress["next_delay"] = round(delay)
                    await _asyncio.sleep(delay)
                    progress["next_delay"] = 0
    except Exception as e:
        logger.error(f"[STAGGERED] photo task {task_id} crashed: {e}")
        progress["errors"].append(f"Task error: {str(e)[:120]}")
    finally:
        progress["status"] = "completed"
        progress["current_phone"] = None
        progress["next_delay"] = 0


async def _staggered_2fa_change(task_id: str, account_ids: list[int], new_password: str, old_passwords: dict[int, str]):
    """Background: change 2FA password on Telegram with staggered delays."""
    import random
    from app.db import async_session_maker

    progress = _bulk_op_progress[task_id]
    try:
        async with async_session_maker() as session:
            for i, aid in enumerate(account_ids):
                account = await session.get(TgAccount, aid)
                if not account or not account.api_id or not account.api_hash:
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue
                if not telegram_engine.session_file_exists(account.phone):
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                progress["current_phone"] = account.phone
                try:
                    kwargs = _account_connect_kwargs(account)
                    await telegram_engine.connect(aid, **kwargs)
                    client = telegram_engine.get_client(aid)
                    if client and await client.is_user_authorized():
                        old_pw = old_passwords.get(aid, '')
                        await client.edit_2fa(current_password=old_pw, new_password=new_password)
                        progress["synced"] += 1
                    await telegram_engine.disconnect(aid)
                except Exception as e:
                    progress["errors"].append(f"{account.phone}: {str(e)[:80]}")
                    logger.warning(f"[STAGGERED] 2FA change failed for {account.phone}: {e}")

                progress["completed"] += 1

                if i < len(account_ids) - 1:
                    delay = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
                    progress["next_delay"] = round(delay)
                    await _asyncio.sleep(delay)
                    progress["next_delay"] = 0
    except Exception as e:
        logger.error(f"[STAGGERED] 2FA task {task_id} crashed: {e}")
        progress["errors"].append(f"Task error: {str(e)[:120]}")
    finally:
        progress["status"] = "completed"
        progress["current_phone"] = None
        progress["next_delay"] = 0


async def _staggered_privacy_update(task_id: str, account_ids: list[int], active_params: dict):
    """Background: update privacy settings on Telegram with staggered delays."""
    import random
    from app.db import async_session_maker
    from telethon import functions, types

    PRIVACY_MAP = {
        "everyone": [types.InputPrivacyValueAllowAll()],
        "contacts": [types.InputPrivacyValueAllowContacts()],
        "nobody": [types.InputPrivacyValueDisallowAll()],
    }
    KEY_MAP = {
        "last_online": types.InputPrivacyKeyStatusTimestamp,
        "phone_visibility": types.InputPrivacyKeyPhoneNumber,
        "profile_pic_visibility": types.InputPrivacyKeyProfilePhoto,
        "bio_visibility": types.InputPrivacyKeyAbout,
        "forwards_visibility": types.InputPrivacyKeyForwards,
        "calls": types.InputPrivacyKeyPhoneCall,
        "private_messages": types.InputPrivacyKeyChatInvite,
    }

    progress = _bulk_op_progress[task_id]
    try:
        async with async_session_maker() as session:
            for i, aid in enumerate(account_ids):
                account = await session.get(TgAccount, aid)
                if not account or not account.api_id or not telegram_engine.session_file_exists(account.phone):
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                progress["current_phone"] = account.phone
                try:
                    kwargs = _account_connect_kwargs(account)
                    await telegram_engine.connect(aid, **kwargs)
                    client = telegram_engine.get_client(aid)
                    if not client or not await client.is_user_authorized():
                        progress["skipped"] += 1
                        progress["completed"] += 1
                        continue
                    for key_name, value in active_params.items():
                        if key_name in KEY_MAP:
                            await client(functions.account.SetPrivacyRequest(
                                key=KEY_MAP[key_name](), rules=PRIVACY_MAP[value]
                            ))
                    await telegram_engine.disconnect(aid)
                    progress["synced"] += 1
                except Exception as e:
                    progress["errors"].append(f"{account.phone}: {str(e)[:80]}")

                progress["completed"] += 1

                if i < len(account_ids) - 1:
                    delay = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
                    progress["next_delay"] = round(delay)
                    await _asyncio.sleep(delay)
                    progress["next_delay"] = 0
    except Exception as e:
        logger.error(f"[STAGGERED] privacy task {task_id} crashed: {e}")
    finally:
        progress["status"] = "completed"
        progress["current_phone"] = None
        progress["next_delay"] = 0


async def _staggered_revoke_sessions(task_id: str, account_ids: list[int]):
    """Background: revoke other sessions with staggered delays between accounts.

    Supports both session-file accounts (via telegram_engine) and
    string_session-only accounts (direct TelegramClient + StringSession).
    """
    import random
    from app.db import async_session_maker
    from app.core.config import settings
    from telethon import TelegramClient, functions
    from telethon.sessions import StringSession

    progress = _bulk_op_progress[task_id]
    progress["sessions_killed"] = 0

    fallback_api_id = getattr(settings, "TELEGRAM_CHECKER_API_ID", 0) or 0
    fallback_api_hash = getattr(settings, "TELEGRAM_CHECKER_API_HASH", "") or ""

    try:
        async with async_session_maker() as session:
            for i, aid in enumerate(account_ids):
                account = await session.get(TgAccount, aid)
                if not account:
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                # Determine connection method
                has_session_file = account.api_id and telegram_engine.session_file_exists(account.phone)
                has_string_session = bool(account.string_session)
                api_id = account.api_id or fallback_api_id
                api_hash = account.api_hash or fallback_api_hash

                if not has_session_file and not has_string_session:
                    logger.warning(f"[REVOKE] {account.phone}: no session file and no string_session, skipping")
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                if not api_id or not api_hash:
                    logger.warning(f"[REVOKE] {account.phone}: no api_id/api_hash available, skipping")
                    progress["skipped"] += 1
                    progress["completed"] += 1
                    continue

                progress["current_phone"] = account.phone
                client = None
                used_string_session = False
                try:
                    # Resolve proxy
                    proxy = None
                    if account.assigned_proxy_id:
                        p = await session.get(TgProxy, account.assigned_proxy_id)
                        if p:
                            proxy = {"host": p.host, "port": p.port, "username": p.username,
                                     "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}

                    if has_session_file:
                        kwargs = _account_connect_kwargs(account, proxy)
                        try:
                            await telegram_engine.connect(aid, **kwargs)
                        except Exception as conn_err:
                            logger.warning(f"[REVOKE] {account.phone}: proxy connect failed: {conn_err}, retrying direct")
                            await telegram_engine.disconnect(aid)
                            kwargs_direct = _account_connect_kwargs(account, None)
                            await telegram_engine.connect(aid, **kwargs_direct)
                        client = telegram_engine.get_client(aid)
                    else:
                        # Connect via StringSession directly
                        used_string_session = True
                        proxy_tuple = telegram_engine._proxy_to_tuple(proxy)
                        try:
                            client = TelegramClient(
                                StringSession(account.string_session),
                                api_id, api_hash,
                                device_model=account.device_model or "PC 64bit",
                                system_version=account.system_version or "Windows 10",
                                app_version=account.app_version or "6.5.1 x64",
                                lang_code=account.lang_code or "en",
                                system_lang_code=account.system_lang_code or "en-US",
                                proxy=proxy_tuple,
                                timeout=30,
                                connection_retries=2,
                            )
                            await client.connect()
                        except Exception as conn_err:
                            logger.warning(f"[REVOKE] {account.phone}: proxy connect failed: {conn_err}, retrying direct")
                            try:
                                await client.disconnect()
                            except Exception:
                                pass
                            client = TelegramClient(
                                StringSession(account.string_session),
                                api_id, api_hash,
                                device_model=account.device_model or "PC 64bit",
                                system_version=account.system_version or "Windows 10",
                                app_version=account.app_version or "6.5.1 x64",
                                lang_code=account.lang_code or "en",
                                system_lang_code=account.system_lang_code or "en-US",
                                timeout=30,
                                connection_retries=2,
                            )
                            await client.connect()
                        logger.info(f"[REVOKE] {account.phone}: connected via StringSession")

                    if not client or not await client.is_user_authorized():
                        logger.warning(f"[REVOKE] {account.phone}: not authorized, skipping")
                        progress["skipped"] += 1
                        progress["completed"] += 1
                        if used_string_session and client:
                            await client.disconnect()
                        continue

                    result = await client(functions.auth.GetAuthorizationsRequest())
                    all_sessions = result.authorizations
                    other_sessions = [a for a in all_sessions if not a.current]
                    logger.info(f"[REVOKE] {account.phone}: found {len(all_sessions)} total sessions, {len(other_sessions)} other")

                    if not other_sessions:
                        logger.info(f"[REVOKE] {account.phone}: no other sessions to revoke")
                        if used_string_session:
                            await client.disconnect()
                        else:
                            await telegram_engine.disconnect(aid)
                        progress["synced"] += 1
                        progress["completed"] += 1
                        if i < len(account_ids) - 1:
                            delay = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
                            progress["next_delay"] = round(delay)
                            await _asyncio.sleep(delay)
                            progress["next_delay"] = 0
                        continue

                    # Try individual session termination first
                    killed = 0
                    individual_errors = 0
                    for auth in other_sessions:
                        try:
                            await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                            killed += 1
                            logger.info(f"[REVOKE] {account.phone}: killed session device={auth.device_model} platform={auth.platform}")
                        except Exception as e:
                            individual_errors += 1
                            logger.warning(f"[REVOKE] {account.phone}: failed to kill session device={auth.device_model}: {e}")
                        await _asyncio.sleep(0.5)

                    # Fallback: if individual revocations all failed, use nuclear option
                    if killed == 0 and individual_errors > 0:
                        logger.warning(f"[REVOKE] {account.phone}: individual revoke failed for all {individual_errors} sessions, trying ResetAuthorizationsRequest")
                        try:
                            await client(functions.auth.ResetAuthorizationsRequest())
                            killed = len(other_sessions)
                            logger.info(f"[REVOKE] {account.phone}: ResetAuthorizationsRequest succeeded — terminated all other sessions")
                        except Exception as e:
                            logger.error(f"[REVOKE] {account.phone}: ResetAuthorizationsRequest also failed: {e}")

                    if used_string_session:
                        await client.disconnect()
                    else:
                        await telegram_engine.disconnect(aid)
                    progress["sessions_killed"] = progress.get("sessions_killed", 0) + killed
                    progress["synced"] += 1
                    logger.info(f"[REVOKE] {account.phone}: done — killed {killed}/{len(other_sessions)} sessions")
                except Exception as e:
                    logger.error(f"[REVOKE] {account.phone}: error: {e}")
                    progress["errors"].append(f"{account.phone}: {str(e)[:80]}")
                    if used_string_session and client:
                        try:
                            await client.disconnect()
                        except Exception:
                            pass

                progress["completed"] += 1

                if i < len(account_ids) - 1:
                    delay = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
                    progress["next_delay"] = round(delay)
                    await _asyncio.sleep(delay)
                    progress["next_delay"] = 0
    except Exception as e:
        logger.error(f"[STAGGERED] revoke task {task_id} crashed: {e}")
    finally:
        progress["status"] = "completed"
        progress["current_phone"] = None
        progress["next_delay"] = 0


@router.get("/accounts/bulk-op-progress/{task_id}")
async def get_bulk_op_progress(task_id: str):
    """Get progress of a staggered bulk operation."""
    progress = _bulk_op_progress.get(task_id)
    if not progress:
        raise HTTPException(404, "Task not found")
    return progress


@router.post("/accounts/bulk-randomize-names")
async def bulk_randomize_names(
    data: TgBulkAccountIds,
    category: str = Query("male_en", description="Name category: male_pt, female_pt, male_en, female_en, male_ru, female_ru"),
    session: AsyncSession = Depends(get_session),
):
    """Assign random names from chosen category + auto-generate username."""
    import random
    preset = NAME_PRESETS.get(category)
    if not preset:
        raise HTTPException(400, f"Unknown category: {category}. Options: {list(NAME_PRESETS.keys())}")

    updated = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        first = random.choice(preset["first"])
        last = random.choice(preset["last"])
        username = _generate_username(first, last)
        account.first_name = first
        account.last_name = last
        account.username = username
        updated.append({"id": aid, "first_name": first, "last_name": last, "username": username})
    await session.flush()
    # Launch staggered TG sync in background (30-120s between accounts)
    account_ids = [u["id"] for u in updated]
    task_id = _create_bulk_task(len(account_ids), "sync_names")
    _asyncio.get_event_loop().create_task(_staggered_profile_sync(task_id, account_ids))
    return {"ok": True, "count": len(updated), "task_id": task_id, "updated": updated}


@router.post("/accounts/bulk-set-photo")
async def bulk_set_photo(
    account_ids_json: str = Form(...),
    photos: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Set profile photos — save locally (immediate) + staggered TG upload (background).
    - 1 photo uploaded → same photo for all accounts
    - N photos uploaded → randomly distributed across accounts
    """
    import json, random, os

    account_ids = json.loads(account_ids_json)
    photo_contents = []
    for p in photos:
        content = await p.read()
        photo_contents.append((p.filename or "photo.jpg", content))

    updated = 0
    photo_map: dict[int, str] = {}  # account_id → photo_path (for staggered TG upload)
    photos_dir = "/app/tg_photos"
    os.makedirs(photos_dir, exist_ok=True)

    for aid in account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        # Pick photo: 1 photo → same for all, N → random
        if len(photo_contents) == 1:
            fname, content = photo_contents[0]
        else:
            fname, content = random.choice(photo_contents)

        # Save to disk — always as .jpg, remove old variants
        photo_path = f"{photos_dir}/{account.phone}.jpg"
        for old_ext in ['.jpg', '.jpeg', '.png', '.jfif', '.webp']:
            old_path = f"{photos_dir}/{account.phone}{old_ext}"
            if os.path.exists(old_path):
                os.remove(old_path)
        with open(photo_path, "wb") as f:
            f.write(content)
        account.profile_photo_path = photo_path
        photo_map[aid] = photo_path
        updated += 1

    await session.commit()
    # Launch staggered TG photo upload in background
    task_id = _create_bulk_task(updated, "set_photo")
    _asyncio.get_event_loop().create_task(_staggered_photo_upload(task_id, account_ids, photo_map))
    return {"ok": True, "count": updated, "task_id": task_id, "photos_uploaded": len(photo_contents)}


async def _auto_sync_accounts(account_ids: list[int], session: AsyncSession):
    """Auto-sync profile to Telegram for given accounts. Silently skips failures."""
    import logging
    log = logging.getLogger(__name__)
    synced = 0
    for aid in account_ids:
        account = await session.get(TgAccount, aid)
        if not account or not account.api_id or not account.api_hash:
            continue
        if not telegram_engine.session_file_exists(account.phone):
            continue
        try:
            kwargs = _account_connect_kwargs(account)
            await telegram_engine.connect(aid, **kwargs)
            await telegram_engine.update_profile(
                aid,
                first_name=account.first_name or "",
                last_name=account.last_name or "",
                about=account.bio or "",
                username=account.username or None,
            )
            await telegram_engine.disconnect(aid)
            synced += 1
        except Exception as e:
            log.warning(f"Auto-sync failed for {account.phone}: {e}")
    return synced


@router.post("/accounts/bulk-sync-profile")
async def bulk_sync_profile(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Sync profile (name, bio, username) to Telegram — staggered with delays."""
    task_id = _create_bulk_task(len(data.account_ids), "sync_profile")
    _asyncio.get_event_loop().create_task(_staggered_profile_sync(task_id, data.account_ids))
    return {"ok": True, "task_id": task_id, "count": len(data.account_ids)}


@router.post("/accounts/bulk-set-bio")
async def bulk_set_bio(data: TgBulkAccountIds, bio: str = Query(...),
                        session: AsyncSession = Depends(get_session)):
    """Set bio for multiple accounts + staggered sync to Telegram."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.bio = bio
    await session.flush()
    # Launch staggered TG sync in background
    task_id = _create_bulk_task(len(data.account_ids), "sync_bio")
    _asyncio.get_event_loop().create_task(_staggered_profile_sync(task_id, data.account_ids))
    return {"ok": True, "count": len(data.account_ids), "task_id": task_id}


@router.post("/accounts/bulk-set-2fa")
async def bulk_set_2fa(data: TgBulkAccountIds, password: str = Query(...),
                        session: AsyncSession = Depends(get_session)):
    """Set 2FA password for multiple accounts — DB update immediate, TG change staggered."""
    updated = 0
    old_passwords = {}
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        old_passwords[aid] = account.two_fa_password or ''
        account.two_fa_password = password
        updated += 1
    await session.flush()
    # Launch staggered TG 2FA change in background
    task_id = _create_bulk_task(updated, "set_2fa")
    _asyncio.get_event_loop().create_task(_staggered_2fa_change(task_id, data.account_ids, password, old_passwords))
    return {"ok": True, "updated": updated, "task_id": task_id}


@router.post("/accounts/bulk-set-status")
async def bulk_set_status(data: TgBulkAccountIds, status: str = Query(...),
                           session: AsyncSession = Depends(get_session)):
    """Set status for multiple accounts."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.status = TgAccountStatus(status)
    return {"ok": True, "count": len(data.account_ids)}


@router.post("/accounts/bulk-update-privacy")
async def bulk_update_privacy(
    data: TgBulkAccountIds,
    last_online: Optional[str] = Query(None, description="everyone/contacts/nobody"),
    phone_visibility: Optional[str] = Query(None),
    profile_pic_visibility: Optional[str] = Query(None),
    bio_visibility: Optional[str] = Query(None),
    forwards_visibility: Optional[str] = Query(None),
    calls: Optional[str] = Query(None),
    private_messages: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Update privacy settings — staggered with delays between accounts."""
    from telethon import types

    PRIVACY_MAP_KEYS = {"everyone", "contacts", "nobody"}
    params = {
        "last_online": last_online, "phone_visibility": phone_visibility,
        "profile_pic_visibility": profile_pic_visibility, "bio_visibility": bio_visibility,
        "forwards_visibility": forwards_visibility, "calls": calls,
        "private_messages": private_messages,
    }
    active_params = {k: v for k, v in params.items() if v and v in PRIVACY_MAP_KEYS}

    if not active_params:
        return {"ok": True, "message": "No privacy settings specified"}

    task_id = _create_bulk_task(len(data.account_ids), "privacy")
    _asyncio.get_event_loop().create_task(_staggered_privacy_update(task_id, data.account_ids, active_params))
    return {"ok": True, "task_id": task_id, "count": len(data.account_ids)}


@router.post("/accounts/bulk-revoke-sessions")
async def bulk_revoke_sessions(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Revoke all other sessions — staggered with delays between accounts."""
    task_id = _create_bulk_task(len(data.account_ids), "revoke_sessions")
    _asyncio.get_event_loop().create_task(_staggered_revoke_sessions(task_id, data.account_ids))
    return {"ok": True, "task_id": task_id, "count": len(data.account_ids)}


@router.post("/accounts/bulk-audit-sessions")
async def bulk_audit_sessions(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Audit sessions for selected accounts.

    Detects:
    - Concurrent sessions from other clients (Desktop, mobile) with different api_id
    - Fingerprint ↔ api_id mismatch (Desktop fingerprint but non-official api_id)
    - Total active sessions count
    """
    import asyncio
    from telethon import functions

    results = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account or not account.api_id or not telegram_engine.session_file_exists(account.phone):
            continue

        entry = {
            "account_id": aid,
            "phone": account.phone,
            "api_id": account.api_id,
            "warnings": [],
            "sessions": [],
            "fingerprint_match": True,
        }

        # Check fingerprint ↔ api_id consistency
        is_desktop_fp = (
            account.app_version and "x64" in (account.app_version or "")
            and account.system_version in ("Windows 10", "Windows 11", "macOS 12.6", "macOS 13.4", "macOS 14.2")
        )
        if is_desktop_fp and account.api_id != TDESKTOP_API_ID:
            entry["fingerprint_match"] = False
            entry["warnings"].append(
                f"Desktop fingerprint (device={account.device_model}, os={account.system_version}, "
                f"app={account.app_version}) but api_id={account.api_id} ≠ official tdesktop ({TDESKTOP_API_ID}). "
                f"Telegram may detect this mismatch."
            )

        # Connect and check active sessions
        try:
            proxy = None
            if account.assigned_proxy_id:
                p = await session.get(TgProxy, account.assigned_proxy_id)
                if p:
                    proxy = {"host": p.host, "port": p.port, "username": p.username,
                             "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}
            kwargs = _account_connect_kwargs(account, proxy)
            await telegram_engine.connect(aid, **kwargs)
            client = telegram_engine.get_client(aid)
            if not client or not await client.is_user_authorized():
                entry["warnings"].append("Not authorized — cannot audit sessions")
                results.append(entry)
                continue

            result = await client(functions.auth.GetAuthorizationsRequest())
            for auth in result.authorizations:
                sess_info = {
                    "current": auth.current,
                    "device_model": auth.device_model,
                    "platform": auth.platform,
                    "app_name": auth.app_name,
                    "app_version": auth.app_version,
                    "api_id": auth.api_id,
                    "ip": auth.ip,
                    "country": auth.country,
                    "date_active": str(auth.date_active) if auth.date_active else None,
                }
                entry["sessions"].append(sess_info)

                # Warn about non-current sessions with different api_id
                if not auth.current and auth.api_id != account.api_id:
                    entry["warnings"].append(
                        f"Concurrent session: {auth.app_name} {auth.app_version} on {auth.device_model} "
                        f"(api_id={auth.api_id}, ip={auth.ip}). Different api_id from ours ({account.api_id}). "
                        f"Telegram may flag this as account compromise."
                    )

            entry["total_sessions"] = len(result.authorizations)
            await telegram_engine.disconnect(aid)
            await asyncio.sleep(0.5)

        except Exception as e:
            entry["warnings"].append(f"Audit failed: {str(e)[:120]}")

        results.append(entry)

    accounts_with_warnings = [r for r in results if r["warnings"]]
    return {
        "ok": True,
        "total_audited": len(results),
        "accounts_with_warnings": len(accounts_with_warnings),
        "results": results,
    }


@router.post("/accounts/bulk-reauthorize")
async def bulk_reauthorize(
    data: TgBulkAccountIds,
    new_2fa: Optional[str] = Query(None),
    close_old_sessions: bool = Query(True),
    session: AsyncSession = Depends(get_session),
):
    """Re-authorize accounts with randomized device params + optionally new 2FA."""
    import asyncio
    import random

    reauthed = 0
    errors = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account or not account.api_id or not telegram_engine.session_file_exists(account.phone):
            continue
        try:
            # Randomize device params
            account.device_model = random.choice(DEVICE_PRESETS)
            account.system_version = random.choice(SYSTEM_VERSIONS)
            account.app_version = random.choice(APP_VERSIONS)

            # Resolve proxy
            proxy = None
            if account.assigned_proxy_id:
                p = await session.get(TgProxy, account.assigned_proxy_id)
                if p:
                    proxy = {"host": p.host, "port": p.port, "username": p.username,
                             "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}
            kwargs = _account_connect_kwargs(account, proxy)
            await telegram_engine.connect(aid, **kwargs)
            client = telegram_engine.get_client(aid)
            if not client or not await client.is_user_authorized():
                continue

            # Close other sessions
            if close_old_sessions:
                from telethon import functions
                try:
                    result = await client(functions.auth.GetAuthorizationsRequest())
                    for auth in result.authorizations:
                        if not auth.current:
                            try:
                                await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                                logger.info(f"[REAUTH] {account.phone}: killed session device={auth.device_model}")
                            except Exception as e:
                                logger.warning(f"[REAUTH] {account.phone}: failed to kill session: {e}")
                            await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"[REAUTH] {account.phone}: session revoke failed: {e}")

            # Set new 2FA
            if new_2fa:
                try:
                    await client.edit_2fa(current_password=account.two_fa_password or '', new_password=new_2fa)
                    account.two_fa_password = new_2fa
                except Exception as e:
                    errors.append(f"{account.phone}: 2FA change failed: {str(e)[:30]}")

            await telegram_engine.disconnect(aid)
            account.last_connected_at = func.now()
            reauthed += 1
        except Exception as e:
            errors.append(f"{account.phone}: {str(e)[:50]}")

    return {"ok": True, "reauthed": reauthed, "errors": errors}


@router.get("/accounts/name-presets")
async def get_name_presets():
    """Return available name categories."""
    return {
        "categories": [
            {"key": "male_en", "label": "Male (English)", "count": len(NAME_PRESETS["male_en"]["first"])},
            {"key": "female_en", "label": "Female (English)", "count": len(NAME_PRESETS["female_en"]["first"])},
            {"key": "male_pt", "label": "Male (Portuguese)", "count": len(NAME_PRESETS["male_pt"]["first"])},
            {"key": "female_pt", "label": "Female (Portuguese)", "count": len(NAME_PRESETS["female_pt"]["first"])},
            {"key": "male_ru", "label": "Male (Russian)", "count": len(NAME_PRESETS["male_ru"]["first"])},
            {"key": "female_ru", "label": "Female (Russian)", "count": len(NAME_PRESETS["female_ru"]["first"])},
        ]
    }


@router.post("/accounts/import-teleraptor", response_model=TgTeleRaptorImportResponse)
async def import_teleraptor_accounts(data: TgTeleRaptorImportRequest,
                                      session: AsyncSession = Depends(get_session)):
    """Bulk import accounts from TeleRaptor JSON format."""
    from datetime import datetime as dt

    added = 0
    skipped = 0
    errors = []

    for i, raw in enumerate(data.accounts):
        phone = (raw.phone or "").strip()
        if not phone:
            errors.append(f"Account #{i+1}: missing phone")
            continue

        # Check duplicate
        existing = await session.execute(select(TgAccount).where(TgAccount.phone == phone))
        if existing.scalar():
            skipped += 1
            continue

        # Map spamblock
        sb_map = {"no": TgSpamblockType.NONE, "some": TgSpamblockType.TEMPORARY, "permanent": TgSpamblockType.PERMANENT}
        spamblock_type = sb_map.get(raw.spamblock or "no", TgSpamblockType.NONE)
        status = TgAccountStatus.SPAMBLOCKED if spamblock_type != TgSpamblockType.NONE else TgAccountStatus.ACTIVE

        # Parse last_connect_date
        last_connected = None
        if raw.last_connect_date:
            try:
                last_connected = dt.fromisoformat(raw.last_connect_date).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        # Auto-generate unique fingerprint when TeleRaptor data lacks one
        fp = _generate_random_fingerprint()
        account = TgAccount(
            phone=phone,
            username=raw.username,
            first_name=raw.first_name,
            last_name=raw.last_name,
            api_id=raw.app_id,
            api_hash=raw.app_hash,
            device_model=raw.sdk or fp["device_model"],
            system_version=raw.device or fp["system_version"],
            app_version=raw.app_version or fp["app_version"],
            lang_code=raw.lang_pack or fp["lang_code"],
            system_lang_code=raw.system_lang_pack or fp["system_lang_code"],
            two_fa_password=raw.twoFA,
            session_file=raw.session_file,
            status=status,
            spamblock_type=spamblock_type,
            total_messages_sent=raw.stats_spam_count or 0,
            last_connected_at=last_connected,
            country_code=_detect_country(phone),
            telegram_user_id=raw.tgid,
            session_created_at=_parse_session_date(raw.register_time, raw.tgid, raw.reg_date) or last_connected or func.now(),
            telegram_created_at=_parse_session_date(raw.register_time, raw.tgid, raw.reg_date) or (_parse_session_date(None, raw.tgid) if raw.tgid else None),
        )
        session.add(account)
        added += 1

    if added > 0:
        await session.flush()

    return TgTeleRaptorImportResponse(added=added, skipped=skipped, errors=errors)


@router.get("/accounts/{account_id}/campaigns")
async def get_account_campaigns(account_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgCampaign)
        .join(TgCampaignAccount, TgCampaignAccount.campaign_id == TgCampaign.id)
        .where(TgCampaignAccount.account_id == account_id)
        .order_by(desc(TgCampaign.created_at))
    )
    campaigns = result.scalars().all()
    return [{"id": c.id, "name": c.name, "status": c.status.value} for c in campaigns]


@router.get("/accounts/{account_id}/analytics")
async def get_account_analytics(account_id: int, session: AsyncSession = Depends(get_session)):
    """Account messaging analytics — daily sent/replies/errors for 7d and 30d."""
    from datetime import datetime, timedelta
    from sqlalchemy import cast, Date

    now = datetime.utcnow()
    d30 = now - timedelta(days=30)
    d7 = now - timedelta(days=7)

    # Daily breakdown for last 30 days
    daily_q = await session.execute(
        select(
            cast(TgOutreachMessage.sent_at, Date).label("day"),
            TgOutreachMessage.status,
            func.count(TgOutreachMessage.id),
        ).where(
            TgOutreachMessage.account_id == account_id,
            TgOutreachMessage.sent_at >= d30,
        ).group_by("day", TgOutreachMessage.status).order_by("day")
    )
    daily_rows = daily_q.all()

    # Build daily map
    daily = {}
    for day, status, cnt in daily_rows:
        ds = day.isoformat()
        if ds not in daily:
            daily[ds] = {"date": ds, "sent": 0, "failed": 0, "spamblocked": 0}
        st = status.value if hasattr(status, "value") else status
        if st == "sent":
            daily[ds]["sent"] += cnt
        elif st in ("failed", "bounced"):
            daily[ds]["failed"] += cnt
        elif st == "spamblocked":
            daily[ds]["spamblocked"] += cnt

    # Daily replies breakdown
    from app.models.telegram_outreach import TgIncomingReply
    daily_replies_q = await session.execute(
        select(
            cast(TgIncomingReply.received_at, Date).label("day"),
            func.count(TgIncomingReply.id),
        ).where(
            TgIncomingReply.account_id == account_id,
            TgIncomingReply.received_at >= d30,
        ).group_by("day").order_by("day")
    )
    for day, cnt in daily_replies_q.all():
        ds = day.isoformat()
        if ds not in daily:
            daily[ds] = {"date": ds, "sent": 0, "failed": 0, "spamblocked": 0, "replies": 0}
        daily[ds]["replies"] = cnt

    # Ensure all daily entries have replies key
    for d in daily.values():
        d.setdefault("replies", 0)

    # Unique replies
    replies_30 = (await session.execute(
        select(func.count(func.distinct(TgIncomingReply.recipient_id))).where(
            TgIncomingReply.account_id == account_id,
            TgIncomingReply.received_at >= d30,
        )
    )).scalar() or 0
    replies_7 = (await session.execute(
        select(func.count(func.distinct(TgIncomingReply.recipient_id))).where(
            TgIncomingReply.account_id == account_id,
            TgIncomingReply.received_at >= d7,
        )
    )).scalar() or 0

    # Unique sent / errors
    def _count(since, statuses):
        return select(func.count(func.distinct(TgOutreachMessage.recipient_id))).where(
            TgOutreachMessage.account_id == account_id,
            TgOutreachMessage.sent_at >= since,
            TgOutreachMessage.status.in_(statuses),
        )

    sent_7 = (await session.execute(_count(d7, [TgMessageStatus.SENT]))).scalar() or 0
    sent_30 = (await session.execute(_count(d30, [TgMessageStatus.SENT]))).scalar() or 0
    errors_7 = (await session.execute(_count(d7, [TgMessageStatus.SPAMBLOCKED]))).scalar() or 0
    errors_30 = (await session.execute(_count(d30, [TgMessageStatus.SPAMBLOCKED]))).scalar() or 0

    return {
        "daily": sorted(daily.values(), key=lambda x: x["date"]),
        "sent_7d": sent_7,
        "sent_30d": sent_30,
        "replies_7d": replies_7,
        "replies_30d": replies_30,
        "errors_7d": errors_7,
        "errors_30d": errors_30,
    }


@router.get("/accounts/analytics/overview")
async def get_accounts_analytics_overview(session: AsyncSession = Depends(get_session)):
    """Aggregate messaging analytics across ALL accounts — daily sent/replies/errors for 7d and 30d."""
    from datetime import datetime, timedelta
    from sqlalchemy import cast, Date

    now = datetime.utcnow()
    d30 = now - timedelta(days=30)
    d7 = now - timedelta(days=7)

    # Daily breakdown for last 30 days (all accounts)
    daily_q = await session.execute(
        select(
            cast(TgOutreachMessage.sent_at, Date).label("day"),
            TgOutreachMessage.status,
            func.count(TgOutreachMessage.id),
        ).where(
            TgOutreachMessage.sent_at >= d30,
        ).group_by("day", TgOutreachMessage.status).order_by("day")
    )
    daily_rows = daily_q.all()

    daily: dict = {}
    for day, status, cnt in daily_rows:
        ds = day.isoformat()
        if ds not in daily:
            daily[ds] = {"date": ds, "sent": 0, "failed": 0, "spamblocked": 0, "replies": 0}
        st = status.value if hasattr(status, "value") else status
        if st == "sent":
            daily[ds]["sent"] += cnt
        elif st in ("failed", "bounced"):
            daily[ds]["failed"] += cnt
        elif st == "spamblocked":
            daily[ds]["spamblocked"] += cnt

    # Daily replies (all accounts)
    from app.models.telegram_outreach import TgIncomingReply
    daily_replies_q = await session.execute(
        select(
            cast(TgIncomingReply.received_at, Date).label("day"),
            func.count(TgIncomingReply.id),
        ).where(
            TgIncomingReply.received_at >= d30,
        ).group_by("day").order_by("day")
    )
    for day, cnt in daily_replies_q.all():
        ds = day.isoformat()
        if ds not in daily:
            daily[ds] = {"date": ds, "sent": 0, "failed": 0, "spamblocked": 0, "replies": 0}
        daily[ds]["replies"] = cnt

    for d in daily.values():
        d.setdefault("replies", 0)

    # Unique sent (distinct recipients)
    sent_7 = (await session.execute(
        select(func.count(func.distinct(TgOutreachMessage.recipient_id))).where(
            TgOutreachMessage.sent_at >= d7,
            TgOutreachMessage.status.in_([TgMessageStatus.SENT]),
        )
    )).scalar() or 0
    sent_30 = (await session.execute(
        select(func.count(func.distinct(TgOutreachMessage.recipient_id))).where(
            TgOutreachMessage.sent_at >= d30,
            TgOutreachMessage.status.in_([TgMessageStatus.SENT]),
        )
    )).scalar() or 0

    # Unique replies (distinct recipients)
    replies_7 = (await session.execute(
        select(func.count(func.distinct(TgIncomingReply.recipient_id))).where(
            TgIncomingReply.received_at >= d7,
        )
    )).scalar() or 0
    replies_30 = (await session.execute(
        select(func.count(func.distinct(TgIncomingReply.recipient_id))).where(
            TgIncomingReply.received_at >= d30,
        )
    )).scalar() or 0

    # Spamblock errors (distinct recipients)
    errors_7 = (await session.execute(
        select(func.count(func.distinct(TgOutreachMessage.recipient_id))).where(
            TgOutreachMessage.sent_at >= d7,
            TgOutreachMessage.status.in_([TgMessageStatus.SPAMBLOCKED]),
        )
    )).scalar() or 0
    errors_30 = (await session.execute(
        select(func.count(func.distinct(TgOutreachMessage.recipient_id))).where(
            TgOutreachMessage.sent_at >= d30,
            TgOutreachMessage.status.in_([TgMessageStatus.SPAMBLOCKED]),
        )
    )).scalar() or 0

    return {
        "daily": sorted(daily.values(), key=lambda x: x["date"]),
        "sent_7d": sent_7,
        "sent_30d": sent_30,
        "replies_7d": replies_7,
        "replies_30d": replies_30,
        "errors_7d": errors_7,
        "errors_30d": errors_30,
    }


# ═══════════════════════════════════════════════════════════════════════
# MULTI-FORMAT IMPORT & CONVERSION
# ═══════════════════════════════════════════════════════════════════════

from app.services.tg_account_manager import (
    extract_files_from_upload, match_json_session_pairs, detect_tdata_in_files,
    save_session_file, save_tdata_folder, get_session_path,
    convert_session_to_tdata, convert_tdata_to_session, package_tdata_as_zip,
)


@router.post("/accounts/import-bundle")
async def import_account_bundle(
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Import accounts from mixed file uploads: .json, .session, .zip (containing both).
    Auto-matches JSON+session pairs by phone number. Saves sessions to server.
    """
    from datetime import datetime as dt

    # Read all files
    raw_files = []
    for f in files:
        content = await f.read()
        raw_files.append((f.filename or "unknown", content))

    # Extract (handles .zip)
    all_files = extract_files_from_upload(raw_files)

    # Check for tdata
    tdata_files = detect_tdata_in_files(all_files)

    # Match JSON + session pairs
    pairs = match_json_session_pairs(all_files)

    added = 0
    skipped = 0
    sessions_saved = 0
    string_sessions_created = 0
    errors = []

    for pair in pairs:
        phone = pair["phone"].strip()
        if not phone:
            continue

        json_data = pair["json_data"]

        # Check duplicate
        existing = await session.execute(select(TgAccount).where(TgAccount.phone == phone))
        existing_acc = existing.scalar()

        if existing_acc:
            # If account exists but we have a new session, save it
            if pair["has_session"]:
                save_session_file(phone, pair["session_bytes"])
                existing_acc.session_file = phone
                sessions_saved += 1

                # Extract StringSession and create/update TelegramDMAccount
                api_id = existing_acc.api_id or json_data.get("app_id")
                api_hash = existing_acc.api_hash or json_data.get("app_hash")
                if api_id and api_hash:
                    ss = await _extract_and_save_string_session(
                        pair["session_bytes"], phone, api_id, api_hash,
                        existing_acc, session,
                    )
                    if ss:
                        string_sessions_created += 1

            skipped += 1
            continue

        # Map spamblock
        sb_map = {"no": TgSpamblockType.NONE, "some": TgSpamblockType.TEMPORARY,
                  "permanent": TgSpamblockType.PERMANENT}
        spamblock_type = sb_map.get(json_data.get("spamblock", "no"), TgSpamblockType.NONE)
        status = TgAccountStatus.SPAMBLOCKED if spamblock_type != TgSpamblockType.NONE else TgAccountStatus.ACTIVE

        last_connected = None
        if json_data.get("last_connect_date"):
            try:
                last_connected = dt.fromisoformat(json_data["last_connect_date"]).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        # Auto-generate unique fingerprint when JSON data lacks one
        fp = _generate_random_fingerprint()
        account = TgAccount(
            phone=phone,
            username=json_data.get("username"),
            first_name=json_data.get("first_name"),
            last_name=json_data.get("last_name"),
            api_id=json_data.get("app_id"),
            api_hash=json_data.get("app_hash"),
            device_model=json_data.get("sdk") or fp["device_model"],
            system_version=json_data.get("device") or fp["system_version"],
            app_version=json_data.get("app_version") or fp["app_version"],
            lang_code=json_data.get("lang_pack") or fp["lang_code"],
            system_lang_code=json_data.get("system_lang_pack") or fp["system_lang_code"],
            two_fa_password=json_data.get("twoFA"),
            session_file=phone if pair["has_session"] else None,
            status=status,
            spamblock_type=spamblock_type,
            total_messages_sent=json_data.get("stats_spam_count", 0) or 0,
            last_connected_at=last_connected,
            country_code=_detect_country(phone),
            session_created_at=last_connected or func.now(),
        )
        session.add(account)

        # Save session file + extract StringSession
        if pair["has_session"]:
            save_session_file(phone, pair["session_bytes"])
            sessions_saved += 1

            # Extract StringSession and create TelegramDMAccount
            api_id = json_data.get("app_id")
            api_hash = json_data.get("app_hash")
            if api_id and api_hash:
                ss = await _extract_and_save_string_session(
                    pair["session_bytes"], phone, api_id, api_hash,
                    account, session,
                )
                if ss:
                    string_sessions_created += 1

        added += 1

    if added > 0:
        await session.flush()

    # Download avatars for all accounts with sessions (best-effort, background)
    avatars_fetched = 0
    all_accounts = await session.execute(select(TgAccount).where(TgAccount.session_file.isnot(None)))
    for acc in all_accounts.scalars().all():
        photo_path = f"/app/tg_photos/{acc.phone}.jpg"
        import os
        if os.path.exists(photo_path):
            continue
        if not telegram_engine.session_file_exists(acc.phone):
            continue
        try:
            kwargs = _account_connect_kwargs(acc)
            client = await telegram_engine.connect(acc.id, **kwargs)
            if await client.is_user_authorized():
                me = await client.get_me()
                if me:
                    from pathlib import Path
                    Path(photo_path).parent.mkdir(parents=True, exist_ok=True)
                    downloaded = await client.download_profile_photo(me, file=photo_path)
                    if downloaded:
                        avatars_fetched += 1
            await telegram_engine.disconnect(acc.id)
        except Exception:
            try:
                await telegram_engine.disconnect(acc.id)
            except Exception:
                pass

    return {
        "added": added,
        "skipped": skipped,
        "sessions_saved": sessions_saved,
        "string_sessions_created": string_sessions_created,
        "total_files": len(all_files),
        "pairs_found": len(pairs),
        "errors": errors,
        "has_tdata": tdata_files is not None,
        "avatars_fetched": avatars_fetched,
    }


@router.post("/accounts/fetch-missing-avatars")
async def fetch_missing_avatars(session: AsyncSession = Depends(get_session)):
    """Download profile photos for all accounts that don't have one yet."""
    import os
    from pathlib import Path
    fetched = 0
    errors_list = []
    result_accs = await session.execute(select(TgAccount).where(TgAccount.session_file.isnot(None)))
    for acc in result_accs.scalars().all():
        photo_path = f"/app/tg_photos/{acc.phone}.jpg"
        if os.path.exists(photo_path):
            continue
        if not telegram_engine.session_file_exists(acc.phone):
            continue
        try:
            kwargs = _account_connect_kwargs(acc)
            client = await telegram_engine.connect(acc.id, **kwargs)
            if await client.is_user_authorized():
                me = await client.get_me()
                if me:
                    Path(photo_path).parent.mkdir(parents=True, exist_ok=True)
                    downloaded = await client.download_profile_photo(me, file=photo_path)
                    if downloaded:
                        fetched += 1
            await telegram_engine.disconnect(acc.id)
        except Exception as e:
            errors_list.append(f"{acc.phone}: {str(e)[:40]}")
            try:
                await telegram_engine.disconnect(acc.id)
            except Exception:
                pass
    return {"ok": True, "fetched": fetched, "errors": errors_list}


@router.post("/accounts/{account_id}/convert-to-tdata")
async def convert_account_to_tdata(account_id: int, session: AsyncSession = Depends(get_session)):
    """Convert account's .session to tdata format. Returns download info."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    # Ensure session has auth data by connecting first
    if account.api_id and account.api_hash and telegram_engine.session_file_exists(account.phone):
        try:
            await telegram_engine.connect(
                account_id, phone=account.phone, api_id=account.api_id, api_hash=account.api_hash,
                device_model=account.device_model or "PC 64bit", system_version=account.system_version or "Windows 10",
                app_version=account.app_version or "6.5.1 x64", lang_code=account.lang_code or "en",
                system_lang_code=account.system_lang_code or "en-US",
            )
            await telegram_engine.disconnect(account_id)
        except Exception:
            pass

    try:
        tdata_path = await convert_session_to_tdata(
            account.phone,
            api_id=account.api_id or 2040,
            api_hash=account.api_hash or "b18441a1ff607e10a989891a5462e627",
        )
        return {"ok": True, "phone": account.phone, "tdata_path": str(tdata_path)}
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Conversion failed: {e}")


@router.get("/accounts/{account_id}/download-tdata")
async def download_tdata(account_id: int, session: AsyncSession = Depends(get_session)):
    """Download tdata as ZIP."""
    from fastapi.responses import Response

    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    try:
        zip_bytes = await package_tdata_as_zip(account.phone)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="tdata_{account.phone}.zip"'},
        )
    except FileNotFoundError:
        raise HTTPException(404, "No tdata available. Convert first.")


@router.get("/accounts/{account_id}/download-session")
async def download_session_file(account_id: int, session: AsyncSession = Depends(get_session)):
    """Download .session file."""
    from fastapi.responses import Response

    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    session_path = get_session_path(account.phone)
    if not session_path:
        raise HTTPException(404, "No .session file available")

    with open(session_path, "rb") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{account.phone}.session"'},
    )


@router.post("/accounts/{account_id}/convert-from-tdata")
async def convert_account_from_tdata(account_id: int, session: AsyncSession = Depends(get_session)):
    """Convert account's tdata to .session format."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    # Disconnect active Telethon clients to release .session SQLite lock
    try:
        await telegram_engine.disconnect(account_id)
    except Exception:
        pass
    # Also disconnect DM accounts with same phone (just in case)
    try:
        dm_result = await session.execute(
            select(TelegramDMAccount.id).where(TelegramDMAccount.phone == account.phone)
        )
        for (dm_id,) in dm_result.all():
            try:
                await telegram_dm_service.disconnect_account(dm_id)
            except Exception:
                pass
    except Exception:
        pass
    # Small delay for lock release
    import asyncio as _aio
    await _aio.sleep(0.5)

    try:
        session_path = await convert_tdata_to_session(
            account.phone,
            api_id=account.api_id or 2040,
            api_hash=account.api_hash or "b18441a1ff607e10a989891a5462e627",
        )
        account.session_file = account.phone
        return {"ok": True, "phone": account.phone, "session_path": str(session_path)}
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Conversion failed: {e}")


@router.post("/accounts/{account_id}/upload-tdata")
async def upload_tdata(account_id: int, files: list[UploadFile] = File(...),
                        session: AsyncSession = Depends(get_session)):
    """Upload tdata files for an account (or a ZIP containing them)."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    raw = []
    for f in files:
        content = await f.read()
        raw.append((f.filename or "file", content))

    all_files = extract_files_from_upload(raw)
    save_tdata_folder(account.phone, all_files)

    return {"ok": True, "files_saved": len(all_files), "phone": account.phone}


# ═══════════════════════════════════════════════════════════════════════
# CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns", response_model=TgCampaignListResponse)
async def list_campaigns(
    project_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(TgCampaign)
    if project_id is not None:
        query = query.where(TgCampaign.project_id == project_id)
    query = query.order_by(desc(TgCampaign.created_at))
    result = await session.execute(query)
    campaigns = result.scalars().all()
    items = []
    for c in campaigns:
        acc_count_q = await session.execute(
            select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.campaign_id == c.id)
        )
        replies_count_q = await session.execute(
            select(func.count(TgIncomingReply.id)).where(TgIncomingReply.campaign_id == c.id)
        )
        items.append(TgCampaignResponse(
            id=c.id, project_id=c.project_id, name=c.name, status=c.status.value,
            campaign_type=c.campaign_type or "one_time",
            segment_filters=c.segment_filters,
            segment_last_synced_at=c.segment_last_synced_at,
            daily_message_limit=c.daily_message_limit,
            timezone=c.timezone, send_from_hour=c.send_from_hour, send_to_hour=c.send_to_hour,
            delay_between_sends_min=c.delay_between_sends_min,
            delay_between_sends_max=c.delay_between_sends_max,
            delay_randomness_percent=c.delay_randomness_percent,
            spamblock_errors_to_skip=c.spamblock_errors_to_skip,
            followup_priority=c.followup_priority,
            tags=c.tags or [],
            crm_tag_on_reply=c.crm_tag_on_reply or [],
            crm_status_on_reply=c.crm_status_on_reply,
            crm_owner_on_reply=c.crm_owner_on_reply,
            crm_auto_create_contact=c.crm_auto_create_contact if c.crm_auto_create_contact is not None else True,
            messages_sent_today=c.messages_sent_today,
            total_messages_sent=c.total_messages_sent,
            total_recipients=c.total_recipients,
            accounts_count=acc_count_q.scalar() or 0,
            replies_count=replies_count_q.scalar() or 0,
            created_at=c.created_at, updated_at=c.updated_at,
        ))
    return TgCampaignListResponse(items=items, total=len(items))


@router.post("/campaigns", response_model=TgCampaignResponse)
async def create_campaign(data: TgCampaignCreate, session: AsyncSession = Depends(get_session)):
    campaign = TgCampaign(
        project_id=data.project_id,
        name=data.name, daily_message_limit=data.daily_message_limit,
        timezone=data.timezone, send_from_hour=data.send_from_hour, send_to_hour=data.send_to_hour,
        delay_between_sends_min=data.delay_between_sends_min,
        delay_between_sends_max=data.delay_between_sends_max,
        delay_randomness_percent=data.delay_randomness_percent,
        spamblock_errors_to_skip=data.spamblock_errors_to_skip,
        followup_priority=data.followup_priority,
        campaign_type=data.campaign_type or "one_time",
        segment_filters=data.segment_filters.model_dump() if data.segment_filters else None,
        tags=data.tags or [],
        crm_tag_on_reply=data.crm_tag_on_reply or [],
        crm_status_on_reply=data.crm_status_on_reply,
        crm_owner_on_reply=data.crm_owner_on_reply,
        crm_auto_create_contact=data.crm_auto_create_contact,
    )
    session.add(campaign)
    await session.flush()
    # Auto-create empty sequence
    seq = TgSequence(campaign_id=campaign.id, name=f"{data.name} Sequence")
    session.add(seq)
    await session.flush()

    return TgCampaignResponse(
        id=campaign.id, name=campaign.name, status="draft",
        campaign_type=campaign.campaign_type or "one_time",
        segment_filters=campaign.segment_filters,
        segment_last_synced_at=campaign.segment_last_synced_at,
        daily_message_limit=campaign.daily_message_limit,
        timezone=campaign.timezone, send_from_hour=campaign.send_from_hour,
        send_to_hour=campaign.send_to_hour,
        delay_between_sends_min=campaign.delay_between_sends_min,
        delay_between_sends_max=campaign.delay_between_sends_max,
        delay_randomness_percent=campaign.delay_randomness_percent,
        spamblock_errors_to_skip=campaign.spamblock_errors_to_skip,
        followup_priority=campaign.followup_priority,
        tags=campaign.tags or [],
        crm_tag_on_reply=campaign.crm_tag_on_reply or [],
        crm_status_on_reply=campaign.crm_status_on_reply,
        crm_owner_on_reply=campaign.crm_owner_on_reply,
        crm_auto_create_contact=campaign.crm_auto_create_contact,
        accounts_count=0, created_at=campaign.created_at, updated_at=campaign.updated_at,
    )


@router.put("/campaigns/{campaign_id}", response_model=TgCampaignResponse)
async def update_campaign(campaign_id: int, data: TgCampaignUpdate, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    await session.flush()
    acc_count_q = await session.execute(
        select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.campaign_id == campaign.id)
    )
    return TgCampaignResponse(
        id=campaign.id, name=campaign.name, status=campaign.status.value,
        campaign_type=campaign.campaign_type or "one_time",
        segment_filters=campaign.segment_filters,
        segment_last_synced_at=campaign.segment_last_synced_at,
        daily_message_limit=campaign.daily_message_limit,
        timezone=campaign.timezone, send_from_hour=campaign.send_from_hour,
        send_to_hour=campaign.send_to_hour,
        delay_between_sends_min=campaign.delay_between_sends_min,
        delay_between_sends_max=campaign.delay_between_sends_max,
        delay_randomness_percent=campaign.delay_randomness_percent,
        spamblock_errors_to_skip=campaign.spamblock_errors_to_skip,
        followup_priority=campaign.followup_priority,
        tags=campaign.tags or [],
        crm_tag_on_reply=campaign.crm_tag_on_reply or [],
        crm_status_on_reply=campaign.crm_status_on_reply,
        crm_owner_on_reply=campaign.crm_owner_on_reply,
        crm_auto_create_contact=campaign.crm_auto_create_contact,
        messages_sent_today=campaign.messages_sent_today,
        total_messages_sent=campaign.total_messages_sent,
        total_recipients=campaign.total_recipients,
        accounts_count=acc_count_q.scalar() or 0,
        created_at=campaign.created_at, updated_at=campaign.updated_at,
    )


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await session.delete(campaign)
    return {"ok": True}


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status != TgCampaignStatus.DRAFT and campaign.status != TgCampaignStatus.PAUSED:
        raise HTTPException(400, f"Cannot start campaign with status {campaign.status.value}")

    # For dynamic campaigns, auto-sync segment on start
    if campaign.campaign_type == "dynamic" and campaign.segment_filters and campaign.segment_filters.get("filters"):
        q = _build_segment_query(campaign.segment_filters)
        result = await session.execute(q)
        contacts = result.scalars().all()
        existing_q = await session.execute(
            select(TgRecipient.username).where(TgRecipient.campaign_id == campaign_id)
        )
        existing_usernames = {r.lower() for r in existing_q.scalars().all()}
        bl_q = await session.execute(select(TgBlacklist.username))
        blacklisted = {r.lower() for r in bl_q.scalars().all()}
        for contact in contacts:
            uname = (contact.username or "").lower()
            if not uname or uname in existing_usernames or uname in blacklisted:
                continue
            session.add(TgRecipient(
                campaign_id=campaign_id, username=contact.username,
                first_name=contact.first_name, company_name=contact.company_name,
                custom_variables=contact.custom_data or {},
            ))
            existing_usernames.add(uname)
        campaign.segment_last_synced_at = _dt.utcnow()
        total_q = await session.execute(
            select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
        )
        campaign.total_recipients = total_q.scalar() or 0

    campaign.status = TgCampaignStatus.ACTIVE
    return {"ok": True, "status": "active"}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    campaign.status = TgCampaignStatus.PAUSED
    return {"ok": True, "status": "paused"}


# ── Dynamic segment helpers ────────────────────────────────────────────

def _build_segment_query(filters_data: dict) -> "Select":
    """Build a SQLAlchemy query to find TgContacts matching segment filters."""
    logic = filters_data.get("logic", "AND")
    filters = filters_data.get("filters", [])
    if not filters:
        return select(TgContact)

    conditions = []
    for f in filters:
        field = f.get("field", "")
        op = f.get("operator", "eq")
        val = f.get("value")

        if field == "status":
            vals = val if isinstance(val, list) else [val]
            if op == "in":
                conditions.append(TgContact.status.in_(vals))
            elif op == "not_in":
                conditions.append(~TgContact.status.in_(vals))
        elif field == "tags":
            vals = val if isinstance(val, list) else [val]
            if op == "contains_any":
                # JSONB ?| operator: tags contain ANY of the values
                tag_conds = [TgContact.tags.op("?")(v) for v in vals]
                conditions.append(or_(*tag_conds) if tag_conds else sa_text("true"))
            elif op == "contains_all":
                tag_conds = [TgContact.tags.op("?")(v) for v in vals]
                conditions.append(and_(*tag_conds) if tag_conds else sa_text("true"))
        elif field == "owner":
            # Owner stored in custom_data->>'owner'
            owner_col = TgContact.custom_data["owner"].astext
            if op == "eq":
                conditions.append(owner_col == val)
            elif op == "neq":
                conditions.append(owner_col != val)
            elif op == "in":
                vals = val if isinstance(val, list) else [val]
                conditions.append(owner_col.in_(vals))
        elif field.startswith("custom:"):
            # Custom field: "custom:<field_id>"
            field_id = int(field.split(":")[1])
            sub = select(TgCrmLeadFieldValue.lead_id).where(
                TgCrmLeadFieldValue.field_id == field_id,
            )
            if op == "eq":
                sub = sub.where(TgCrmLeadFieldValue.value == str(val))
            elif op == "neq":
                sub = sub.where(TgCrmLeadFieldValue.value != str(val))
            elif op == "in":
                vals = val if isinstance(val, list) else [val]
                sub = sub.where(TgCrmLeadFieldValue.value.in_([str(v) for v in vals]))
            conditions.append(TgContact.id.in_(sub))
        elif field == "campaign":
            # Filter by campaign participation — campaigns is JSONB array of {id, name}
            vals = val if isinstance(val, list) else [val]
            camp_conds = [TgContact.campaigns.op("@>")(f'[{{"id": {v}}}]') for v in vals]
            if op == "in":
                conditions.append(or_(*camp_conds) if camp_conds else sa_text("true"))
            elif op == "not_in":
                conditions.append(~or_(*camp_conds) if camp_conds else sa_text("true"))

    q = select(TgContact)
    if logic == "OR":
        q = q.where(or_(*conditions) if conditions else sa_text("true"))
    else:
        q = q.where(and_(*conditions) if conditions else sa_text("true"))
    return q


@router.post("/campaigns/{campaign_id}/segment-preview")
async def segment_preview(campaign_id: int, session: AsyncSession = Depends(get_session)):
    """Preview how many CRM contacts match the campaign's segment filters."""
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.segment_filters:
        return {"total": 0, "contacts": []}
    q = _build_segment_query(campaign.segment_filters)
    count_q = await session.execute(select(func.count()).select_from(q.subquery()))
    total = count_q.scalar() or 0
    # Return first 50 contacts for preview
    preview_q = await session.execute(q.limit(50))
    contacts = [{"id": c.id, "username": c.username, "first_name": c.first_name,
                 "status": c.status.value if hasattr(c.status, 'value') else c.status,
                 "tags": c.tags or []}
                for c in preview_q.scalars().all()]
    return {"total": total, "contacts": contacts}


@router.post("/campaigns/{campaign_id}/sync-segment")
async def sync_segment(campaign_id: int, session: AsyncSession = Depends(get_session)):
    """Resolve dynamic segment and add new matching contacts as pending recipients."""
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.campaign_type != "dynamic":
        raise HTTPException(400, "Only dynamic campaigns can sync segments")
    if not campaign.segment_filters or not campaign.segment_filters.get("filters"):
        raise HTTPException(400, "No segment filters configured")

    q = _build_segment_query(campaign.segment_filters)
    result = await session.execute(q)
    contacts = result.scalars().all()

    # Get existing recipient usernames to avoid duplicates
    existing_q = await session.execute(
        select(TgRecipient.username).where(TgRecipient.campaign_id == campaign_id)
    )
    existing_usernames = {r.lower() for r in existing_q.scalars().all()}

    # Also check blacklist
    bl_q = await session.execute(select(TgBlacklist.username))
    blacklisted = {r.lower() for r in bl_q.scalars().all()}

    added = 0
    for contact in contacts:
        uname = (contact.username or "").lower()
        if not uname or uname in existing_usernames or uname in blacklisted:
            continue
        recipient = TgRecipient(
            campaign_id=campaign_id,
            username=contact.username,
            first_name=contact.first_name,
            company_name=contact.company_name,
            custom_variables=contact.custom_data or {},
        )
        session.add(recipient)
        existing_usernames.add(uname)
        added += 1

    campaign.segment_last_synced_at = _dt.utcnow()
    # Update total_recipients
    total_q = await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )
    campaign.total_recipients = total_q.scalar() or 0  # auto-flush makes added visible
    await session.flush()

    return {"ok": True, "added": added, "total_recipients": campaign.total_recipients,
            "synced_at": campaign.segment_last_synced_at.isoformat() if campaign.segment_last_synced_at else None}


@router.get("/campaigns/{campaign_id}/stats", response_model=TgCampaignStatsResponse)
async def get_campaign_stats(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    stats = {}
    for st in TgRecipientStatus:
        count_q = await session.execute(
            select(func.count(TgRecipient.id))
            .where(TgRecipient.campaign_id == campaign_id, TgRecipient.status == st)
        )
        stats[st.value] = count_q.scalar() or 0

    return TgCampaignStatsResponse(
        total_recipients=campaign.total_recipients,
        pending=stats.get("pending", 0),
        in_sequence=stats.get("in_sequence", 0),
        completed=stats.get("completed", 0),
        replied=stats.get("replied", 0),
        failed=stats.get("failed", 0),
        bounced=stats.get("bounced", 0),
        total_messages_sent=campaign.total_messages_sent,
        messages_sent_today=campaign.messages_sent_today,
    )


@router.get("/campaigns/{campaign_id}/step-stats")
async def get_campaign_step_stats(
    campaign_id: int,
    period: Optional[str] = Query(None, description="7d, 30d, or custom"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
):
    """Per-step analytics: sent, read, replied counts for each sequence step.
    Optional period filtering: period=7d|30d|custom with from_date/to_date."""
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Compute date range filter
    date_from = None
    date_to = None
    if period == "7d":
        date_from = _dt.utcnow() - _td(days=7)
    elif period == "30d":
        date_from = _dt.utcnow() - _td(days=30)
    elif period == "custom":
        if from_date:
            date_from = _dt.fromisoformat(from_date)
        if to_date:
            date_to = _dt.fromisoformat(to_date + "T23:59:59") if "T" not in to_date else _dt.fromisoformat(to_date)

    # Get sequence steps ordered
    seq_q = await session.execute(
        select(TgSequence).where(TgSequence.campaign_id == campaign_id)
    )
    sequence = seq_q.scalar()
    if not sequence:
        return {"steps": [], "totals": {"sent": 0, "read": 0, "replied": 0, "total_recipients": 0}, "period": period}

    steps_q = await session.execute(
        select(TgSequenceStep)
        .where(TgSequenceStep.sequence_id == sequence.id)
        .order_by(TgSequenceStep.step_order)
    )
    steps = steps_q.scalars().all()

    # Build message filters
    msg_filters = [
        TgOutreachMessage.campaign_id == campaign_id,
        TgOutreachMessage.status == TgMessageStatus.SENT,
    ]
    if date_from:
        msg_filters.append(TgOutreachMessage.sent_at >= date_from)
    if date_to:
        msg_filters.append(TgOutreachMessage.sent_at <= date_to)

    # Per-step sent & read counts from outreach messages
    msg_stats_q = await session.execute(
        select(
            TgOutreachMessage.step_id,
            func.count(TgOutreachMessage.id).label("sent"),
            func.count(TgOutreachMessage.read_at).label("read"),
        )
        .where(*msg_filters)
        .group_by(TgOutreachMessage.step_id)
    )
    msg_stats = {row.step_id: {"sent": row.sent, "read": row.read} for row in msg_stats_q}

    # Build reply filters
    reply_msg_filters = [
        TgOutreachMessage.campaign_id == campaign_id,
        TgOutreachMessage.status == TgMessageStatus.SENT,
    ]
    if date_from:
        reply_msg_filters.append(TgOutreachMessage.sent_at >= date_from)
    if date_to:
        reply_msg_filters.append(TgOutreachMessage.sent_at <= date_to)

    reply_date_filters = [TgIncomingReply.campaign_id == campaign_id]
    if date_from:
        reply_date_filters.append(TgIncomingReply.received_at >= date_from)
    if date_to:
        reply_date_filters.append(TgIncomingReply.received_at <= date_to)

    # Per-step replied: for each recipient who replied, attribute to the latest step they received
    latest_step_sub = (
        select(
            TgOutreachMessage.recipient_id,
            func.max(TgOutreachMessage.step_id).label("last_step_id"),
        )
        .where(*reply_msg_filters)
        .group_by(TgOutreachMessage.recipient_id)
        .subquery()
    )
    reply_correct_q = await session.execute(
        select(
            latest_step_sub.c.last_step_id,
            func.count(func.distinct(TgIncomingReply.recipient_id)).label("replied"),
        )
        .select_from(TgIncomingReply)
        .join(latest_step_sub, TgIncomingReply.recipient_id == latest_step_sub.c.recipient_id)
        .where(*reply_date_filters)
        .group_by(latest_step_sub.c.last_step_id)
    )
    reply_by_step = {row.last_step_id: row.replied for row in reply_correct_q}

    total_sent = 0
    total_read = 0
    total_replied = 0

    result_steps = []
    for step in steps:
        s = msg_stats.get(step.id, {"sent": 0, "read": 0})
        r = reply_by_step.get(step.id, 0)
        total_sent += s["sent"]
        total_read += s["read"]
        total_replied += r
        result_steps.append({
            "step_order": step.step_order,
            "step_id": step.id,
            "delay_days": step.delay_days,
            "sent": s["sent"],
            "read": s["read"],
            "replied": r,
        })

    return {
        "steps": result_steps,
        "totals": {
            "sent": total_sent,
            "read": total_read,
            "replied": total_replied,
            "total_recipients": campaign.total_recipients,
        },
        "period": period,
    }


@router.get("/campaigns/{campaign_id}/analytics/export-csv")
async def export_campaign_analytics_csv(
    campaign_id: int,
    period: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Export campaign analytics as CSV: per-recipient status with step details."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Date range
    date_from = None
    date_to = None
    if period == "7d":
        date_from = _dt.utcnow() - _td(days=7)
    elif period == "30d":
        date_from = _dt.utcnow() - _td(days=30)
    elif period == "custom":
        if from_date:
            date_from = _dt.fromisoformat(from_date)
        if to_date:
            date_to = _dt.fromisoformat(to_date + "T23:59:59") if "T" not in to_date else _dt.fromisoformat(to_date)

    # Get steps
    seq_q = await session.execute(
        select(TgSequence).where(TgSequence.campaign_id == campaign_id)
    )
    sequence = seq_q.scalar()
    steps = []
    if sequence:
        steps_q = await session.execute(
            select(TgSequenceStep)
            .where(TgSequenceStep.sequence_id == sequence.id)
            .order_by(TgSequenceStep.step_order)
        )
        steps = steps_q.scalars().all()

    # Get recipients
    recip_q = await session.execute(
        select(TgRecipient).where(TgRecipient.campaign_id == campaign_id).order_by(TgRecipient.id)
    )
    recipients = recip_q.scalars().all()

    # Get messages with optional date filter
    msg_filters = [TgOutreachMessage.campaign_id == campaign_id, TgOutreachMessage.status == TgMessageStatus.SENT]
    if date_from:
        msg_filters.append(TgOutreachMessage.sent_at >= date_from)
    if date_to:
        msg_filters.append(TgOutreachMessage.sent_at <= date_to)
    msgs_q = await session.execute(select(TgOutreachMessage).where(*msg_filters))
    messages = msgs_q.scalars().all()

    # Index messages by (recipient_id, step_id)
    msg_map: dict[tuple[int, int], TgOutreachMessage] = {}
    for m in messages:
        msg_map[(m.recipient_id, m.step_id)] = m

    # Get replies
    reply_filters = [TgIncomingReply.campaign_id == campaign_id]
    if date_from:
        reply_filters.append(TgIncomingReply.received_at >= date_from)
    if date_to:
        reply_filters.append(TgIncomingReply.received_at <= date_to)
    replies_q = await session.execute(select(TgIncomingReply).where(*reply_filters))
    replies = replies_q.scalars().all()
    replied_recipients = {r.recipient_id for r in replies}

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = ["Username", "First Name", "Company", "Status", "Replied"]
    for step in steps:
        prefix = f"Step {step.step_order}"
        header.extend([f"{prefix} Sent At", f"{prefix} Read At", f"{prefix} Status"])
    writer.writerow(header)

    # Rows
    for r in recipients:
        row = [
            r.username or "",
            r.first_name or "",
            r.company_name or "",
            r.status.value if r.status else "",
            "Yes" if r.id in replied_recipients else "No",
        ]
        for step in steps:
            msg = msg_map.get((r.id, step.id))
            if msg:
                row.append(msg.sent_at.strftime("%Y-%m-%d %H:%M") if msg.sent_at else "")
                row.append(msg.read_at.strftime("%Y-%m-%d %H:%M") if msg.read_at else "")
                row.append("Read" if msg.read_at else "Sent")
            else:
                row.extend(["", "", "Not sent"])
        writer.writerow(row)

    # Summary rows
    writer.writerow([])
    writer.writerow(["=== SUMMARY ==="])
    writer.writerow(["Total Recipients", len(recipients)])
    writer.writerow(["Total Replied", len(replied_recipients)])
    writer.writerow(["Reply Rate", f"{round(len(replied_recipients) / max(len(recipients), 1) * 100, 1)}%"])
    for step in steps:
        step_msgs = [m for m in messages if m.step_id == step.id]
        step_read = sum(1 for m in step_msgs if m.read_at)
        writer.writerow([
            f"Step {step.step_order}",
            f"Sent: {len(step_msgs)}",
            f"Read: {step_read} ({round(step_read / max(len(step_msgs), 1) * 100, 1)}%)",
        ])

    output.seek(0)
    safe_name = _re.sub(r'[^\w\-]', '_', campaign.name or f"campaign_{campaign_id}")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analytics_{safe_name}.csv"'},
    )


# ── Campaign Timeline ─────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/timeline", response_model=TgCampaignTimelineResponse)
async def get_campaign_timeline(
    campaign_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("username"),
    sort_dir: Optional[str] = Query("asc"),
    session: AsyncSession = Depends(get_session),
):
    """Campaign Timeline: per-recipient message status grid across sequence steps."""
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # 1. Get sequence steps
    seq_q = await session.execute(
        select(TgSequence).where(TgSequence.campaign_id == campaign_id)
    )
    sequence = seq_q.scalar()
    timeline_steps: list[TgTimelineStep] = []
    step_id_to_order: dict[int, int] = {}
    if sequence:
        steps_q = await session.execute(
            select(TgSequenceStep)
            .where(TgSequenceStep.sequence_id == sequence.id)
            .order_by(TgSequenceStep.step_order)
        )
        for s in steps_q.scalars().all():
            timeline_steps.append(TgTimelineStep(step_order=s.step_order, step_id=s.id, delay_days=s.delay_days))
            step_id_to_order[s.id] = s.step_order

    # 2. Query recipients with pagination + search + sorting
    base_filter = [TgRecipient.campaign_id == campaign_id]
    if search:
        base_filter.append(TgRecipient.username.ilike(f"%{search}%"))

    count_q = select(func.count(TgRecipient.id)).where(*base_filter)
    total = (await session.execute(count_q)).scalar() or 0

    sort_col = {
        "username": TgRecipient.username,
        "status": TgRecipient.status,
        "first_name": TgRecipient.first_name,
    }.get(sort_by, TgRecipient.username)
    order_fn = asc if sort_dir == "asc" else desc

    recip_q = (
        select(TgRecipient)
        .where(*base_filter)
        .order_by(order_fn(sort_col))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    recip_result = await session.execute(recip_q)
    recipients = recip_result.scalars().all()

    if not recipients:
        return TgCampaignTimelineResponse(steps=timeline_steps, recipients=[], total=total, page=page, page_size=page_size)

    recip_ids = [r.id for r in recipients]
    account_ids = list({r.assigned_account_id for r in recipients if r.assigned_account_id})

    # 3. Bulk-load accounts for phone numbers
    account_phone_map: dict[int, str] = {}
    if account_ids:
        acc_q = await session.execute(
            select(TgAccount.id, TgAccount.phone).where(TgAccount.id.in_(account_ids))
        )
        account_phone_map = {row.id: row.phone for row in acc_q}

    # 4. Bulk-load all outreach messages for these recipients
    msgs_q = await session.execute(
        select(TgOutreachMessage)
        .where(TgOutreachMessage.recipient_id.in_(recip_ids))
        .order_by(TgOutreachMessage.sent_at)
    )
    all_messages = msgs_q.scalars().all()

    # Group messages by recipient_id → step_id
    from collections import defaultdict
    msgs_by_recip: dict[int, dict[int, TgOutreachMessage]] = defaultdict(dict)
    for m in all_messages:
        if m.step_id:
            msgs_by_recip[m.recipient_id][m.step_id] = m

    # 5. Bulk-load incoming replies for these recipients (first reply per recipient)
    replies_q = await session.execute(
        select(TgIncomingReply.recipient_id, func.min(TgIncomingReply.received_at).label("first_reply_at"))
        .where(
            TgIncomingReply.campaign_id == campaign_id,
            TgIncomingReply.recipient_id.in_(recip_ids),
        )
        .group_by(TgIncomingReply.recipient_id)
    )
    reply_times: dict[int, _dt] = {row.recipient_id: row.first_reply_at for row in replies_q}

    # 6. Build timeline rows
    timeline_recipients: list[TgTimelineRecipient] = []
    for r in recipients:
        step_statuses: dict[str, TgTimelineStepStatus] = {}
        recip_msgs = msgs_by_recip.get(r.id, {})
        first_reply_at = reply_times.get(r.id)

        for ts in timeline_steps:
            msg = recip_msgs.get(ts.step_id)
            if msg:
                # Determine status
                if msg.status.value in ("failed", "spamblocked"):
                    step_status = TgTimelineStepStatus(
                        status=msg.status.value,
                        sent_at=msg.sent_at,
                        error_message=msg.error_message,
                    )
                elif first_reply_at and msg.sent_at and first_reply_at >= msg.sent_at:
                    # Check if this is the last step before reply (reply attributed here)
                    later_msg = any(
                        m.sent_at and m.sent_at > msg.sent_at and m.status.value == "sent"
                        for m in recip_msgs.values()
                    )
                    if not later_msg:
                        step_status = TgTimelineStepStatus(
                            status="replied",
                            sent_at=msg.sent_at,
                            read_at=msg.read_at,
                            replied_at=first_reply_at,
                        )
                    elif msg.read_at:
                        step_status = TgTimelineStepStatus(status="read", sent_at=msg.sent_at, read_at=msg.read_at)
                    else:
                        step_status = TgTimelineStepStatus(status="sent", sent_at=msg.sent_at)
                elif msg.read_at:
                    step_status = TgTimelineStepStatus(status="read", sent_at=msg.sent_at, read_at=msg.read_at)
                else:
                    step_status = TgTimelineStepStatus(status="sent", sent_at=msg.sent_at)
            elif ts.step_order == r.current_step + 1 and r.next_message_at:
                step_status = TgTimelineStepStatus(status="scheduled", sent_at=r.next_message_at)
            elif ts.step_order <= r.current_step:
                step_status = TgTimelineStepStatus(status="sent")  # step done but msg not found
            else:
                step_status = TgTimelineStepStatus(status="pending")

            step_statuses[str(ts.step_order)] = step_status

        timeline_recipients.append(TgTimelineRecipient(
            id=r.id,
            username=r.username,
            first_name=r.first_name,
            status=r.status.value,
            assigned_account_id=r.assigned_account_id,
            assigned_account_phone=account_phone_map.get(r.assigned_account_id) if r.assigned_account_id else None,
            next_message_at=r.next_message_at,
            steps=step_statuses,
        ))

    return TgCampaignTimelineResponse(
        steps=timeline_steps,
        recipients=timeline_recipients,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Campaign Accounts ──────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/accounts")
async def get_campaign_accounts(campaign_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgAccount)
        .join(TgCampaignAccount, TgCampaignAccount.account_id == TgAccount.id)
        .where(TgCampaignAccount.campaign_id == campaign_id)
    )
    accounts = result.scalars().all()
    return [{"id": a.id, "phone": a.phone, "username": a.username,
             "messages_sent_today": a.messages_sent_today,
             "daily_message_limit": a.daily_message_limit,
             "status": a.status.value} for a in accounts]


@router.put("/campaigns/{campaign_id}/accounts")
async def set_campaign_accounts(campaign_id: int, account_ids: list[int],
                                 session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Remove existing (SQL-level delete, no ORM identity-map issues)
    await session.execute(
        sa_delete(TgCampaignAccount).where(TgCampaignAccount.campaign_id == campaign_id)
    )

    # Add new (bulk insert)
    if account_ids:
        await session.execute(
            sa_insert(TgCampaignAccount),
            [{"campaign_id": campaign_id, "account_id": aid} for aid in account_ids],
        )

    return {"ok": True, "count": len(account_ids)}


# ═══════════════════════════════════════════════════════════════════════
# RECIPIENTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/recipients", response_model=TgRecipientListResponse)
async def list_recipients(
    campaign_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(TgRecipient).where(TgRecipient.campaign_id == campaign_id)
    count_query = select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)

    if status:
        query = query.where(TgRecipient.status == status)
        count_query = count_query.where(TgRecipient.status == status)

    total = (await session.execute(count_query)).scalar() or 0
    query = query.order_by(TgRecipient.id).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)

    return TgRecipientListResponse(
        items=[TgRecipientResponse.model_validate(r) for r in result.scalars().all()],
        total=total, page=page, page_size=page_size,
    )


@router.post("/campaigns/{campaign_id}/recipients/upload-text")
async def upload_recipients_text(campaign_id: int, data: TgRecipientUploadText,
                                  session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Load blacklist for filtering
    bl_rows = (await session.execute(select(TgBlacklist.username))).scalars().all()
    blacklisted = set(bl_rows)

    added = 0
    blacklisted_count = 0
    added_usernames = []
    for line in data.raw_text.strip().splitlines():
        username = line.strip().lstrip("@")
        if not username:
            continue
        # Check blacklist (case-insensitive)
        if username.lower() in blacklisted:
            blacklisted_count += 1
            continue
        # Skip duplicates
        existing = await session.execute(
            select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id, TgRecipient.username == username
            )
        )
        if existing.scalar():
            continue
        session.add(TgRecipient(campaign_id=campaign_id, username=username))
        added += 1
        added_usernames.append(username.lower())
        try:
            crm_q = await session.execute(select(TgContact).where(TgContact.username == username))
            if not crm_q.scalar():
                session.add(TgContact(username=username, status=TgContactStatus.COLD,
                    source_campaign_id=campaign_id, campaigns=[{"id": campaign_id, "name": campaign.name}]))
        except Exception:
            pass

    # Count cross-campaign duplicates among added usernames
    cross_dupes = 0
    if added_usernames:
        from sqlalchemy import func as sa_func
        cross_q = await session.execute(
            select(sa_func.count(sa_func.distinct(sa_func.lower(TgRecipient.username)))).where(
                TgRecipient.campaign_id != campaign_id,
                sa_func.lower(TgRecipient.username).in_(added_usernames),
            )
        )
        cross_dupes = cross_q.scalar() or 0

    campaign.total_recipients = (await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )).scalar() or 0

    return {"ok": True, "added": added, "total": campaign.total_recipients,
            "blacklisted": blacklisted_count, "cross_duplicates": cross_dupes}


@router.post("/campaigns/{campaign_id}/recipients/add-from-crm")
async def add_recipients_from_crm(campaign_id: int, data: dict,
                                   session: AsyncSession = Depends(get_session)):
    """Add CRM contacts as campaign recipients by their IDs."""
    contact_ids = data.get("contact_ids", [])
    if not contact_ids:
        raise HTTPException(400, "No contacts selected")

    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Load blacklist
    bl_rows = (await session.execute(select(TgBlacklist.username))).scalars().all()
    blacklisted = set(bl_rows)

    # Load selected contacts
    contacts_result = await session.execute(
        select(TgContact).where(TgContact.id.in_(contact_ids))
    )
    contacts = contacts_result.scalars().all()

    added = 0
    blacklisted_count = 0
    skipped = 0
    added_usernames = []
    for contact in contacts:
        username = contact.username
        if not username:
            continue
        if username.lower() in blacklisted:
            blacklisted_count += 1
            continue
        # Skip duplicates
        existing = await session.execute(
            select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id, TgRecipient.username == username
            )
        )
        if existing.scalar():
            skipped += 1
            continue
        session.add(TgRecipient(
            campaign_id=campaign_id,
            username=username,
            first_name=contact.first_name,
            company_name=contact.company_name,
        ))
        added += 1
        added_usernames.append(username.lower())

    # Count cross-campaign duplicates
    cross_dupes = 0
    if added_usernames:
        from sqlalchemy import func as sa_func
        cross_q = await session.execute(
            select(sa_func.count(sa_func.distinct(sa_func.lower(TgRecipient.username)))).where(
                TgRecipient.campaign_id != campaign_id,
                sa_func.lower(TgRecipient.username).in_(added_usernames),
            )
        )
        cross_dupes = cross_q.scalar() or 0

    campaign.total_recipients = (await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )).scalar() or 0

    return {"ok": True, "added": added, "skipped": skipped, "total": campaign.total_recipients,
            "blacklisted": blacklisted_count, "cross_duplicates": cross_dupes}


@router.post("/campaigns/{campaign_id}/recipients/upload-csv")
async def upload_recipients_csv(campaign_id: int, file: UploadFile = File(...),
                                 session: AsyncSession = Depends(get_session)):
    """Upload CSV and return column names for mapping."""
    import csv
    import io

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    headers = next(reader, [])
    preview_rows = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        preview_rows.append(dict(zip(headers, row)))

    return {"columns": headers, "preview": preview_rows, "file_name": file.filename}


@router.post("/campaigns/{campaign_id}/recipients/map-columns")
async def map_csv_columns(campaign_id: int,
                           file: UploadFile = File(...),
                           mapping_json: str = Form(...),
                           session: AsyncSession = Depends(get_session)):
    """Import CSV recipients with column mapping. mapping_json is JSON-encoded TgRecipientUploadCSVMapping."""
    import csv
    import io
    import json

    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    mapping = TgRecipientUploadCSVMapping(**json.loads(mapping_json))

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    # Load blacklist for filtering
    bl_rows = (await session.execute(select(TgBlacklist.username))).scalars().all()
    blacklisted = set(bl_rows)

    added = 0
    blacklisted_count = 0
    added_usernames = []
    for row in reader:
        username = row.get(mapping.username_column, "").strip().lstrip("@")
        if not username:
            continue
        # Check blacklist
        if username.lower() in blacklisted:
            blacklisted_count += 1
            continue
        # Skip duplicates
        existing = await session.execute(
            select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id, TgRecipient.username == username
            )
        )
        if existing.scalar():
            continue

        custom_vars = {}
        if mapping.phone_column:
            phone_val = row.get(mapping.phone_column, "").strip()
            if phone_val:
                custom_vars["phone"] = phone_val
        for csv_col, var_name in mapping.custom_columns.items():
            custom_vars[var_name] = row.get(csv_col, "")

        session.add(TgRecipient(
            campaign_id=campaign_id,
            username=username,
            first_name=row.get(mapping.first_name_column, "") if mapping.first_name_column else None,
            company_name=row.get(mapping.company_name_column, "") if mapping.company_name_column else None,
            custom_variables=custom_vars,
        ))
        added += 1
        added_usernames.append(username.lower())

    # Count cross-campaign duplicates
    cross_dupes = 0
    if added_usernames:
        from sqlalchemy import func as sa_func
        cross_q = await session.execute(
            select(sa_func.count(sa_func.distinct(sa_func.lower(TgRecipient.username)))).where(
                TgRecipient.campaign_id != campaign_id,
                sa_func.lower(TgRecipient.username).in_(added_usernames),
            )
        )
        cross_dupes = cross_q.scalar() or 0

    campaign.total_recipients = (await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )).scalar() or 0

    return {"ok": True, "added": added, "total": campaign.total_recipients,
            "blacklisted": blacklisted_count, "cross_duplicates": cross_dupes}


@router.delete("/campaigns/{campaign_id}/recipients/{recipient_id}")
async def delete_recipient(campaign_id: int, recipient_id: int, session: AsyncSession = Depends(get_session)):
    recipient = await session.get(TgRecipient, recipient_id)
    if not recipient or recipient.campaign_id != campaign_id:
        raise HTTPException(404, "Recipient not found")
    await session.delete(recipient)
    return {"ok": True}


@router.post("/campaigns/{campaign_id}/recipients/check-duplicates", response_model=TgCheckDuplicatesResponse)
async def check_cross_campaign_duplicates(campaign_id: int, data: TgCheckDuplicatesRequest,
                                           session: AsyncSession = Depends(get_session)):
    """Check if any usernames already exist as recipients in OTHER campaigns."""
    if not data.usernames:
        return TgCheckDuplicatesResponse(total_checked=0, duplicates_count=0, duplicates=[])

    # Normalize usernames
    clean = [u.strip().lstrip("@").lower() for u in data.usernames if u.strip()]
    if not clean:
        return TgCheckDuplicatesResponse(total_checked=0, duplicates_count=0, duplicates=[])

    # Find recipients with matching usernames in OTHER campaigns
    from sqlalchemy import func as sa_func
    result = await session.execute(
        select(
            TgRecipient.username,
            TgRecipient.current_step,
            TgRecipient.status,
            TgRecipient.assigned_account_id,
            TgCampaign.id.label("cid"),
            TgCampaign.name.label("cname"),
            TgCampaign.status.label("cstatus"),
            TgCampaign.total_recipients.label("ctotal"),
        )
        .join(TgCampaign, TgRecipient.campaign_id == TgCampaign.id)
        .where(
            TgRecipient.campaign_id != campaign_id,
            sa_func.lower(TgRecipient.username).in_(clean),
        )
    )
    rows = result.all()

    # Resolve account usernames for display
    account_ids = {r.assigned_account_id for r in rows if r.assigned_account_id}
    acc_map = {}
    if account_ids:
        acc_rows = await session.execute(
            select(TgAccount.id, TgAccount.username, TgAccount.first_name)
            .where(TgAccount.id.in_(account_ids))
        )
        for a in acc_rows.all():
            acc_map[a.id] = a.username or a.first_name or f"Account #{a.id}"

    # Get total steps per campaign for completion %
    campaign_ids = {r.cid for r in rows}
    steps_map: dict[int, int] = {}
    if campaign_ids:
        steps_result = await session.execute(
            select(
                TgSequence.campaign_id,
                sa_func.count(TgSequenceStep.id).label("total_steps"),
            )
            .join(TgSequenceStep, TgSequence.id == TgSequenceStep.sequence_id, isouter=True)
            .where(TgSequence.campaign_id.in_(campaign_ids))
            .group_by(TgSequence.campaign_id)
        )
        for s in steps_result.all():
            steps_map[s.campaign_id] = s.total_steps

    # Count completed recipients per campaign for completion %
    completed_map: dict[int, int] = {}
    if campaign_ids:
        completed_result = await session.execute(
            select(
                TgRecipient.campaign_id,
                sa_func.count(TgRecipient.id).label("completed"),
            )
            .where(
                TgRecipient.campaign_id.in_(campaign_ids),
                TgRecipient.status.in_(["completed", "replied"]),
            )
            .group_by(TgRecipient.campaign_id)
        )
        for c in completed_result.all():
            completed_map[c.campaign_id] = c.completed

    duplicates = []
    for r in rows:
        total_steps = steps_map.get(r.cid, 1) or 1
        total_recip = r.ctotal or 1
        completed_count = completed_map.get(r.cid, 0)
        completion_pct = round(completed_count * 100 / total_recip)

        # Build step label: "Step 1 (initial)" or "Step 2 (follow-up 1)"
        step = r.current_step
        if step <= 0:
            step_label = "Not started"
        elif step == 1:
            step_label = "Step 1 (initial)"
        else:
            step_label = f"Step {step} (follow-up {step - 1})"

        duplicates.append(TgDuplicateDetail(
            username=r.username,
            campaign_id=r.cid,
            campaign_name=r.cname,
            campaign_status=r.cstatus.value if hasattr(r.cstatus, 'value') else str(r.cstatus),
            current_step=r.current_step,
            total_steps=total_steps,
            step_label=step_label,
            recipient_status=r.status.value if hasattr(r.status, 'value') else str(r.status),
            campaign_completion_pct=completion_pct,
            assigned_account=acc_map.get(r.assigned_account_id),
        ))

    unique_usernames = {d.username.lower() for d in duplicates}
    return TgCheckDuplicatesResponse(
        total_checked=len(clean),
        duplicates_count=len(unique_usernames),
        duplicates=duplicates,
    )


@router.post("/campaigns/{campaign_id}/recipients/bulk-remove")
async def bulk_remove_recipients(campaign_id: int, data: TgBulkRemoveRecipients,
                                  session: AsyncSession = Depends(get_session)):
    """Remove recipients by username from a campaign."""
    if not data.usernames:
        return {"ok": True, "removed": 0}

    from sqlalchemy import func as sa_func
    clean = [u.strip().lstrip("@").lower() for u in data.usernames if u.strip()]
    if not clean:
        return {"ok": True, "removed": 0}

    result = await session.execute(
        select(TgRecipient)
        .where(
            TgRecipient.campaign_id == campaign_id,
            sa_func.lower(TgRecipient.username).in_(clean),
        )
    )
    recipients = result.scalars().all()
    for r in recipients:
        await session.delete(r)

    # Update campaign total
    campaign = await session.get(TgCampaign, campaign_id)
    if campaign:
        count_result = await session.execute(
            select(sa_func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
        )
        campaign.total_recipients = count_result.scalar() or 0

    return {"ok": True, "removed": len(recipients)}


# ═══════════════════════════════════════════════════════════════════════
# SEQUENCES
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/sequence", response_model=TgSequenceSchema)
async def get_sequence(campaign_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgSequence)
        .where(TgSequence.campaign_id == campaign_id)
        .options(
            selectinload(TgSequence.steps).selectinload(TgSequenceStep.variants)
        )
    )
    seq = result.scalar()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    return TgSequenceSchema(
        id=seq.id, name=seq.name,
        steps=[
            TgSequenceStepSchema(
                id=step.id, step_order=step.step_order, delay_days=step.delay_days,
                message_type=step.message_type or "text",
                variants=[
                    TgStepVariantSchema(
                        id=v.id, variant_label=v.variant_label,
                        message_text=v.message_text, weight_percent=v.weight_percent,
                        media_file_path=v.media_file_path,
                    ) for v in step.variants
                ],
            ) for step in seq.steps
        ],
    )


@router.put("/campaigns/{campaign_id}/sequence", response_model=TgSequenceSchema)
async def update_sequence(campaign_id: int, data: TgSequenceSchema,
                           session: AsyncSession = Depends(get_session)):
    """Replace the entire sequence (steps + variants) for a campaign."""
    result = await session.execute(
        select(TgSequence)
        .where(TgSequence.campaign_id == campaign_id)
        .options(selectinload(TgSequence.steps).selectinload(TgSequenceStep.variants))
    )
    seq = result.scalar()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    if data.name is not None:
        seq.name = data.name

    # Delete existing steps (cascade deletes variants)
    for old_step in seq.steps:
        await session.delete(old_step)
    await session.flush()

    # Create new steps + variants
    new_steps = []
    for step_data in data.steps:
        step = TgSequenceStep(
            sequence_id=seq.id,
            step_order=step_data.step_order,
            delay_days=step_data.delay_days,
            message_type=step_data.message_type,
        )
        session.add(step)
        await session.flush()

        for v_data in step_data.variants:
            variant = TgStepVariant(
                step_id=step.id,
                variant_label=v_data.variant_label,
                message_text=v_data.message_text,
                weight_percent=v_data.weight_percent,
                media_file_path=v_data.media_file_path,
            )
            session.add(variant)

        new_steps.append(step)

    await session.flush()

    # Expire session cache so re-read gets fresh data
    session.expire_all()

    # Re-read and return
    return await get_sequence(campaign_id, session)


@router.post("/campaigns/{campaign_id}/media")
async def upload_campaign_media(campaign_id: int, file: UploadFile = File(...)):
    """Upload a media file (image, video, document, voice) for a campaign sequence step."""
    import os
    media_dir = f"/app/media/campaigns/{campaign_id}"
    os.makedirs(media_dir, exist_ok=True)

    # Sanitize filename
    safe_name = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    file_path = f"{media_dir}/{safe_name}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return {"file_path": file_path, "filename": safe_name, "size": len(content)}


@router.post("/campaigns/{campaign_id}/sequence/preview", response_model=TgSequencePreviewResponse)
async def preview_sequence(campaign_id: int, data: TgSequencePreviewRequest,
                            session: AsyncSession = Depends(get_session)):
    """Preview rendered messages for a sample recipient."""
    import random
    import re

    # Get sequence
    seq_result = await session.execute(
        select(TgSequence)
        .where(TgSequence.campaign_id == campaign_id)
        .options(selectinload(TgSequence.steps).selectinload(TgSequenceStep.variants))
    )
    seq = seq_result.scalar()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    # Get sample recipient
    recipients = await session.execute(
        select(TgRecipient).where(TgRecipient.campaign_id == campaign_id)
        .offset(data.recipient_index).limit(1)
    )
    recipient = recipients.scalar()

    # Build variable context
    variables = {}
    if recipient:
        variables["first_name"] = recipient.first_name or ""
        variables["company_name"] = recipient.company_name or ""
        variables["username"] = recipient.username or ""
        if recipient.custom_variables:
            variables.update(recipient.custom_variables)

    steps_preview = []
    for step in seq.steps:
        rendered_variants = []
        for v in step.variants:
            # Variables first, then spintax — otherwise {{var}} gets destroyed
            text = _substitute_variables(v.message_text, variables)
            text = _resolve_spintax(text)
            rendered_variants.append({"label": v.variant_label, "text": text})
        steps_preview.append({
            "step_order": step.step_order,
            "delay_days": step.delay_days,
            "rendered_variants": rendered_variants,
        })

    return TgSequencePreviewResponse(steps=steps_preview)


def _resolve_spintax(text: str) -> str:
    """Recursively resolve {option1|option2|option3} spintax."""
    import random
    import re

    pattern = re.compile(r"\{([^{}]+)\}")
    while pattern.search(text):
        text = pattern.sub(lambda m: random.choice(m.group(1).split("|")), text)
    return text


def _substitute_variables(text: str, variables: dict) -> str:
    """Replace {{variable_name}} with values from context."""
    import re
    def replacer(m):
        key = m.group(1).strip()
        return variables.get(key, m.group(0))
    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


# ═══════════════════════════════════════════════════════════════════════
# OUTREACH MESSAGES (log)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/messages", response_model=TgOutreachMessageListResponse)
async def list_campaign_messages(
    campaign_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = (
        select(TgOutreachMessage)
        .where(TgOutreachMessage.campaign_id == campaign_id)
        .options(
            joinedload(TgOutreachMessage.recipient),
            joinedload(TgOutreachMessage.account),
            joinedload(TgOutreachMessage.step),
            joinedload(TgOutreachMessage.variant),
        )
        .order_by(desc(TgOutreachMessage.sent_at))
    )
    count_q = select(func.count(TgOutreachMessage.id)).where(
        TgOutreachMessage.campaign_id == campaign_id
    )
    total = (await session.execute(count_q)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    messages = result.scalars().unique().all()

    items = []
    for m in messages:
        items.append(TgOutreachMessageResponse(
            id=m.id, campaign_id=m.campaign_id,
            recipient_id=m.recipient_id,
            recipient_username=m.recipient.username if m.recipient else None,
            account_id=m.account_id,
            account_phone=m.account.phone if m.account else None,
            step_order=m.step.step_order if m.step else None,
            variant_label=m.variant.variant_label if m.variant else None,
            rendered_text=m.rendered_text,
            status=m.status.value,
            error_message=m.error_message,
            sent_at=m.sent_at,
        ))

    return TgOutreachMessageListResponse(items=items, total=total, page=page, page_size=page_size)


# ═══════════════════════════════════════════════════════════════════════
# TELEGRAM ENGINE — Auth, Check, Profile (Phase 4)
# ═══════════════════════════════════════════════════════════════════════

from app.models.telegram_outreach import TgIncomingReply
from app.schemas.telegram_outreach import TgIncomingReplyResponse, TgIncomingReplyListResponse
from app.services.telegram_engine import telegram_engine, TelegramEngine, session_file_to_string_session
from telethon.sessions import StringSession


async def _get_account_with_proxy(account_id: int, session: AsyncSession) -> tuple:
    """Helper: load account + assigned proxy details."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    if not account.api_id or not account.api_hash:
        raise HTTPException(400, "Account missing api_id / api_hash")

    proxy = None
    if account.assigned_proxy_id:
        from app.models.telegram_outreach import TgProxy
        p = await session.get(TgProxy, account.assigned_proxy_id)
        if p:
            proxy = {"host": p.host, "port": p.port, "username": p.username,
                     "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}

    return account, proxy


def _account_connect_kwargs(account, proxy=None) -> dict:
    return dict(
        phone=account.phone,
        api_id=account.api_id,
        api_hash=account.api_hash,
        device_model=account.device_model or "PC 64bit",
        system_version=account.system_version or "Windows 10",
        app_version=account.app_version or "6.5.1 x64",
        lang_code=account.lang_code or "en",
        system_lang_code=account.system_lang_code or "en-US",
        proxy=proxy,
    )


# ── Session upload ────────────────────────────────────────────────────

@router.get("/accounts/{account_id}/avatar")
async def get_account_avatar(account_id: int, session: AsyncSession = Depends(get_session)):
    """Serve account's Telegram avatar image."""
    from fastapi.responses import FileResponse
    import os

    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    # Check for avatar (try multiple extensions)
    for ext in ['.jpg', '.jpeg', '.png', '.jfif', '.webp']:
        photo_path = f"/app/tg_photos/{account.phone}{ext}"
        if os.path.exists(photo_path):
            mtime = str(int(os.path.getmtime(photo_path)))
            return FileResponse(photo_path, media_type="image/jpeg",
                                headers={"Cache-Control": "no-cache", "ETag": mtime})

    # Check profile_photo_path
    if account.profile_photo_path and os.path.exists(account.profile_photo_path):
        return FileResponse(account.profile_photo_path, media_type="image/jpeg",
                            headers={"Cache-Control": "no-cache"})

    raise HTTPException(404, "No avatar available")


@router.post("/accounts/{account_id}/upload-session")
async def upload_session(account_id: int, file: UploadFile = File(...),
                          session: AsyncSession = Depends(get_session)):
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    content = await file.read()
    await telegram_engine.save_uploaded_session(account.phone, content)
    account.session_file = account.phone

    # Extract StringSession and create/update TelegramDMAccount
    string_session_ok = False
    if account.api_id and account.api_hash:
        ss = await _extract_and_save_string_session(
            content, account.phone, account.api_id, account.api_hash,
            account, session,
        )
        string_session_ok = ss is not None

    return {"ok": True, "session_file": account.phone, "string_session_created": string_session_ok}


# ── Auth flow ─────────────────────────────────────────────────────────


async def _save_session_after_auth(account_id: int, account, session: AsyncSession):
    """After successful auth, save StringSession and user info from get_me()."""
    client = telegram_engine.get_client(account_id)
    if not client:
        return
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            if me:
                account.telegram_user_id = me.id
                if me.username:
                    account.username = me.username
                if me.first_name:
                    account.first_name = me.first_name
                if me.last_name:
                    account.last_name = me.last_name
            account.string_session = StringSession.save(client.session)
            account.session_file = account.phone
            account.status = TgAccountStatus.ACTIVE
            account.last_connected_at = func.now()
            logger.info(f"Session saved for account {account_id} ({account.phone})")
    except Exception as e:
        logger.warning(f"Failed to save session after auth for {account_id}: {e}")


@router.post("/accounts/add-by-phone")
async def add_by_phone(
    phone: str = Query(..., description="Phone number with country code, e.g. 351920619583"),
    two_fa_password: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Create account + auto-generate fingerprint + send auth code in one step."""
    phone = phone.strip().lstrip("+")
    if not phone:
        raise HTTPException(400, "Phone is required")

    # Check duplicate
    existing = await session.execute(select(TgAccount).where(TgAccount.phone == phone))
    if existing.scalar():
        raise HTTPException(409, f"Account with phone {phone} already exists")

    # Generate unique fingerprint using device_fingerprints pool
    from app.services.device_fingerprints import generate_fingerprint
    existing_models_q = await session.execute(select(TgAccount.device_model).where(TgAccount.device_model.isnot(None)))
    existing_models = {r[0] for r in existing_models_q.all()}
    fp = generate_fingerprint(exclude_models=existing_models)

    # Create account with TDesktop credentials
    account = TgAccount(
        phone=phone,
        api_id=TDESKTOP_API_ID,
        api_hash=TDESKTOP_API_HASH,
        device_model=fp["device_model"],
        system_version=fp["system_version"],
        app_version=fp["app_version"],
        lang_code=fp["lang_code"],
        system_lang_code=fp["system_lang_code"],
        two_fa_password=two_fa_password,
        country_code=_detect_country(phone),
        session_created_at=func.now(),
        daily_message_limit=5,
    )
    session.add(account)
    await session.flush()

    # Send auth code
    kwargs = _account_connect_kwargs(account, proxy=None)
    try:
        result = await telegram_engine.send_code(account.id, **kwargs)
    except Exception as e:
        # Rollback the account creation if send_code fails
        await session.delete(account)
        raise HTTPException(400, f"Failed to send code: {e}")

    return {
        "account_id": account.id,
        "phone": account.phone,
        "status": result.get("status", "code_sent"),
        "device_model": fp["device_model"],
    }


@router.post("/accounts/{account_id}/auth/send-code")
async def auth_send_code(account_id: int, session: AsyncSession = Depends(get_session)):
    account, proxy = await _get_account_with_proxy(account_id, session)
    kwargs = _account_connect_kwargs(account, proxy)
    result = await telegram_engine.send_code(account_id, **kwargs)
    return result


@router.post("/accounts/{account_id}/auth/verify-code")
async def auth_verify_code(account_id: int, code: str = Query(...),
                            session: AsyncSession = Depends(get_session)):
    result = await telegram_engine.verify_code(account_id, code)

    if result.get("status") == "authorized":
        account = await session.get(TgAccount, account_id)
        if account:
            await _save_session_after_auth(account_id, account, session)

    return result


@router.post("/accounts/{account_id}/auth/verify-2fa")
async def auth_verify_2fa(account_id: int, password: str = Query(...),
                           session: AsyncSession = Depends(get_session)):
    result = await telegram_engine.verify_2fa(account_id, password)

    if result.get("status") == "authorized":
        account = await session.get(TgAccount, account_id)
        if account:
            if password:
                account.two_fa_password = password
            await _save_session_after_auth(account_id, account, session)

    return result


# ── Health check ──────────────────────────────────────────────────────

@router.post("/accounts/{account_id}/check")
async def check_account(account_id: int, session: AsyncSession = Depends(get_session)):
    account, proxy = await _get_account_with_proxy(account_id, session)

    if not telegram_engine.session_file_exists(account.phone):
        raise HTTPException(400, f"No session file for {account.phone}. Upload a .session file first.")

    kwargs = _account_connect_kwargs(account, proxy)
    result = await telegram_engine.check_account(account_id, **kwargs)

    # Update DB based on check result
    if result.get("authorized"):
        from datetime import datetime

        # Permanent ban detected (Abuse Notifications / self-message fail)
        if result.get("banned"):
            account.status = TgAccountStatus.BANNED
            account.ban_reason = result.get("ban_reason")
            account.banned_at = datetime.utcnow()
        else:
            sb = result.get("spamblock", "unknown")
            if result.get("frozen"):
                # Frozen account — restricted but not fully banned
                account.status = TgAccountStatus.FROZEN
                account.spamblock_type = TgSpamblockType.TEMPORARY
                account.spamblocked_at = datetime.utcnow()
            elif sb in ("temporary", "permanent"):
                account.status = TgAccountStatus.SPAMBLOCKED
                sb_map = {"temporary": TgSpamblockType.TEMPORARY, "permanent": TgSpamblockType.PERMANENT}
                account.spamblock_type = sb_map.get(sb, TgSpamblockType.TEMPORARY)
                account.spamblocked_at = datetime.utcnow()
                if result.get("spamblock_end"):
                    try:
                        account.spamblock_end = datetime.fromisoformat(result["spamblock_end"])
                    except Exception:
                        pass
            elif sb == "none":
                account.status = TgAccountStatus.ACTIVE
                account.spamblock_type = TgSpamblockType.NONE
                account.spamblock_end = None
                account.ban_reason = None
                account.banned_at = None
            # sb == "unknown" — leave current status unchanged, don't mark ACTIVE
        account.last_checked_at = func.now()
        account.last_connected_at = func.now()
        if result.get("username"):
            account.username = result["username"]
        if result.get("first_name"):
            account.first_name = result["first_name"]
        if result.get("last_name") is not None:
            account.last_name = result["last_name"]
        if result.get("avatar_path"):
            account.profile_photo_path = result["avatar_path"]
        if result.get("telegram_user_id"):
            account.telegram_user_id = result["telegram_user_id"]
        if "is_premium" in result:
            account.is_premium = result["is_premium"]
            if not account.is_premium:
                account.daily_message_limit = max(account.daily_message_limit or 5, 5)
            else:
                account.daily_message_limit = max(account.daily_message_limit or 10, 10)
        if result.get("telegram_created_at"):
            try:
                tg_created = datetime.fromisoformat(result["telegram_created_at"])
                if not account.telegram_created_at:
                    account.telegram_created_at = tg_created
                if not account.session_created_at or tg_created < account.session_created_at:
                    account.session_created_at = tg_created
            except Exception:
                pass
    elif result.get("connected") and not result.get("authorized"):
        account.status = TgAccountStatus.DEAD
        account.last_checked_at = func.now()

    # Disconnect after check
    await telegram_engine.disconnect(account_id)

    return result


@router.post("/accounts/bulk-check-live")
async def bulk_check_live(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Check multiple accounts in sequence. Returns per-account results."""
    results = []
    for aid in data.account_ids:
        try:
            account, proxy = await _get_account_with_proxy(aid, session)
            if not telegram_engine.session_file_exists(account.phone):
                results.append({"account_id": aid, "phone": account.phone, "status": "no_session"})
                continue

            kwargs = _account_connect_kwargs(account, proxy)
            check = await telegram_engine.check_account(aid, **kwargs)

            # Update DB
            if check.get("authorized"):
                from datetime import datetime as _dt
                if check.get("banned"):
                    account.status = TgAccountStatus.BANNED
                    account.ban_reason = check.get("ban_reason")
                    account.banned_at = _dt.utcnow()
                else:
                    if check.get("frozen"):
                        account.status = TgAccountStatus.FROZEN
                        account.spamblock_type = TgSpamblockType.TEMPORARY
                        account.spamblocked_at = _dt.utcnow()
                    else:
                        sb = check.get("spamblock", "unknown")
                        sb_map = {"none": TgSpamblockType.NONE, "temporary": TgSpamblockType.TEMPORARY,
                                  "permanent": TgSpamblockType.PERMANENT}
                        if sb in sb_map:
                            account.spamblock_type = sb_map[sb]
                            if sb == "none":
                                account.status = TgAccountStatus.ACTIVE
                            else:
                                account.status = TgAccountStatus.SPAMBLOCKED
                        # sb == "unknown" — leave current status unchanged
                account.last_checked_at = func.now()
                account.last_connected_at = func.now()
                # Fetch telegram_user_id if missing
                if not account.telegram_user_id:
                    try:
                        client = telegram_engine.get_client(aid)
                        me = await client.get_me()
                        if me:
                            account.telegram_user_id = me.id
                            est = _parse_session_date(None, me.id)
                            if est:
                                if not account.session_created_at or est < account.session_created_at:
                                    account.session_created_at = est
                                if not account.telegram_created_at:
                                    account.telegram_created_at = est
                    except Exception:
                        pass
            elif check.get("connected") and not check.get("authorized"):
                account.status = TgAccountStatus.DEAD
                account.last_checked_at = func.now()

            await telegram_engine.disconnect(aid)
            results.append({"account_id": aid, "phone": account.phone, **check})
        except HTTPException as e:
            results.append({"account_id": aid, "error": e.detail})
        except Exception as e:
            results.append({"account_id": aid, "error": str(e)})

    return {"results": results}


@router.post("/accounts/bulk-check-alive")
async def bulk_check_alive(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Alive check: connect + auth + self-message test + SpamBot check.
    Detects frozen/spamblocked/banned accounts. Also fetches telegram_user_id and estimates account age."""
    results = []
    for aid in data.account_ids:
        try:
            account, proxy = await _get_account_with_proxy(aid, session)
            if not telegram_engine.session_file_exists(account.phone):
                results.append({"account_id": aid, "phone": account.phone, "alive": False, "reason": "no_session"})
                continue

            kwargs = _account_connect_kwargs(account, proxy)
            # Try with proxy first; if connection fails, retry direct (no proxy)
            try:
                await telegram_engine.connect(aid, **kwargs)
            except Exception as conn_err:
                logger.warning(f"[ALIVE] {account.phone} proxy connect failed: {conn_err}, retrying direct")
                await telegram_engine.disconnect(aid)
                kwargs_direct = _account_connect_kwargs(account, None)
                await telegram_engine.connect(aid, **kwargs_direct)
            client = telegram_engine.get_client(aid)
            authorized = await client.is_user_authorized()

            if authorized:
                account.last_connected_at = func.now()
                # Fetch tgid + estimate account age
                try:
                    me = await client.get_me()
                    if me:
                        account.telegram_user_id = me.id
                        account.is_premium = getattr(me, "premium", False) or False
                        if not account.telegram_created_at:
                            from app.services.telegram_engine import _estimate_creation_date
                            est = _estimate_creation_date(me.id)
                            if est:
                                from datetime import datetime as _dt
                                account.telegram_created_at = _dt.fromisoformat(est)
                except Exception:
                    pass

                # ── Self-message test: detect frozen / banned ────────
                frozen = False
                banned = False
                ban_reason = None
                try:
                    from telethon import errors as _terr
                    msg = await client.send_message("me", ".")
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                except _terr.UserDeactivatedBanError:
                    banned = True
                    ban_reason = "user_deactivated"
                except (_terr.AuthKeyUnregisteredError, _terr.UserDeactivatedError):
                    banned = True
                    ban_reason = "send_failed"
                except (_terr.UserRestrictedError, _terr.ChatWriteForbiddenError):
                    frozen = True
                except _terr.FloodWaitError:
                    pass  # not a ban
                except Exception as e:
                    err_str = str(e).lower()
                    if "deactivated" in err_str or "banned" in err_str:
                        banned = True
                        ban_reason = "send_failed"
                    elif "restricted" in err_str or "forbidden" in err_str:
                        frozen = True

                if banned:
                    account.status = TgAccountStatus.BANNED
                    results.append({"account_id": aid, "phone": account.phone, "alive": False, "reason": ban_reason or "banned"})
                elif frozen:
                    account.status = TgAccountStatus.FROZEN
                    account.spamblock_type = TgSpamblockType.TEMPORARY
                    results.append({"account_id": aid, "phone": account.phone, "alive": False, "reason": "frozen"})
                else:
                    # ── SpamBot check: detect spamblock/frozen that self-msg missed ──
                    spamblock_detected = False
                    spamblock_reason = None
                    try:
                        spambot = await client.get_entity("@SpamBot")
                        await client.send_message(spambot, "/start")
                        await _asyncio.sleep(2)
                        messages = await client.get_messages(spambot, limit=1)
                        if messages:
                            text = messages[0].text or ""
                            text_lower = text.lower()
                            no_limit_kw = [
                                "no limits", "free as a bird", "not limited",
                                "не ограничен", "всё хорошо", "нет ограничений",
                            ]
                            temp_kw = [
                                "temporary", "will be removed", "will be lifted",
                                "временно", "будет снято", "будет автоматически",
                            ]
                            perm_kw = [
                                "permanent", "forever",
                                "навсегда", "навечно",
                            ]
                            restricted_kw = [
                                "limited", "restricted", "frozen",
                                "ограничен", "заморожен", "заблокирован",
                            ]
                            if any(kw in text_lower for kw in no_limit_kw):
                                account.spamblock_type = TgSpamblockType.NONE
                            elif any(kw in text_lower for kw in temp_kw):
                                spamblock_detected = True
                                account.status = TgAccountStatus.SPAMBLOCKED
                                account.spamblock_type = TgSpamblockType.TEMPORARY
                                spamblock_reason = "spamblocked"
                                date_match = _re.search(
                                    r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})'
                                    r'|(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})'
                                    r'|(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})',
                                    text, _re.IGNORECASE
                                )
                                if date_match:
                                    try:
                                        from dateutil import parser as dateparser
                                        account.spamblock_end = dateparser.parse(date_match.group(0))
                                    except Exception:
                                        pass
                                logger.warning(f"[ALIVE] {account.phone} spamblocked (temporary) — SpamBot: {text[:200]}")
                            elif any(kw in text_lower for kw in perm_kw):
                                spamblock_detected = True
                                account.status = TgAccountStatus.BANNED
                                account.spamblock_type = TgSpamblockType.PERMANENT
                                spamblock_reason = "banned"
                                logger.warning(f"[ALIVE] {account.phone} permanent spamblock — SpamBot: {text[:200]}")
                            elif any(kw in text_lower for kw in restricted_kw):
                                spamblock_detected = True
                                account.status = TgAccountStatus.FROZEN
                                account.spamblock_type = TgSpamblockType.TEMPORARY
                                spamblock_reason = "frozen"
                                logger.warning(f"[ALIVE] {account.phone} frozen/restricted — SpamBot: {text[:200]}")
                        # Clean up SpamBot dialog
                        try:
                            import random
                            await _asyncio.sleep(random.uniform(1, 3))
                            await client.delete_dialog(spambot)
                        except Exception:
                            pass
                    except (_terr.UserRestrictedError, _terr.ChatWriteForbiddenError):
                        spamblock_detected = True
                        spamblock_reason = "frozen"
                        account.status = TgAccountStatus.FROZEN
                        account.spamblock_type = TgSpamblockType.TEMPORARY
                        logger.warning(f"[ALIVE] {account.phone} frozen — cannot message SpamBot")
                    except Exception as e:
                        logger.warning(f"[ALIVE] {account.phone} SpamBot check failed: {e}")

                    if spamblock_detected:
                        results.append({"account_id": aid, "phone": account.phone, "alive": False, "reason": spamblock_reason})
                    else:
                        account.status = TgAccountStatus.ACTIVE
                        account.spamblock_type = TgSpamblockType.NONE
                        results.append({"account_id": aid, "phone": account.phone, "alive": True})
            else:
                account.status = TgAccountStatus.DEAD
                results.append({"account_id": aid, "phone": account.phone, "alive": False, "reason": "not_authorized"})

            await telegram_engine.disconnect(aid)
        except Exception as e:
            logger.error(f"[ALIVE] account {aid} error: {e}")
            results.append({"account_id": aid, "alive": False, "reason": "error", "error": str(e)[:80]})

    alive_count = sum(1 for r in results if r.get("alive"))
    frozen_count = sum(1 for r in results if r.get("reason") == "frozen")
    spamblocked_count = sum(1 for r in results if r.get("reason") == "spamblocked")
    banned_count = sum(1 for r in results if r.get("reason") in ("banned", "user_deactivated", "send_failed"))
    dead_count = sum(1 for r in results if r.get("reason") == "not_authorized")
    error_count = sum(1 for r in results if r.get("reason") == "error")
    logger.info(f"[ALIVE] Done: {len(results)} checked — {alive_count} alive, {frozen_count} frozen, {spamblocked_count} spamblocked, {banned_count} banned, {dead_count} dead, {error_count} errors")
    return {"total": len(results), "alive": alive_count, "frozen": frozen_count + spamblocked_count, "banned": banned_count, "dead": dead_count, "errors": error_count, "results": results}


# ── Profile update ────────────────────────────────────────────────────

@router.post("/accounts/{account_id}/update-profile")
async def update_account_profile(
    account_id: int,
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
    about: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    account, proxy = await _get_account_with_proxy(account_id, session)

    if not telegram_engine.session_file_exists(account.phone):
        raise HTTPException(400, "No session file. Upload first.")

    # Connect if not already
    kwargs = _account_connect_kwargs(account, proxy)
    await telegram_engine.connect(account_id, **kwargs)

    result = await telegram_engine.update_profile(
        account_id,
        first_name=first_name,
        last_name=last_name,
        about=about,
        username=username,
    )

    # Update local DB too
    if first_name is not None:
        account.first_name = first_name
    if last_name is not None:
        account.last_name = last_name
    if about is not None:
        account.bio = about
    if username is not None and not result.get("username_error"):
        account.username = username

    await telegram_engine.disconnect(account_id)

    return result


@router.post("/accounts/{account_id}/check-username")
async def check_username_availability(
    account_id: int,
    username: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Check if a Telegram username is available."""
    account, proxy = await _get_account_with_proxy(account_id, session)
    if not telegram_engine.session_file_exists(account.phone):
        raise HTTPException(400, "No session file")

    kwargs = _account_connect_kwargs(account, proxy)
    try:
        await telegram_engine.connect(account_id, **kwargs)
    except Exception as e:
        raise HTTPException(502, f"Cannot connect to Telegram: {e}")
    try:
        result = await telegram_engine.check_username(account_id, username)
    finally:
        await telegram_engine.disconnect(account_id)
    return result


def _generate_username_candidates(first_name: str, last_name: str) -> list[str]:
    """Generate human-like username candidates from a name."""
    import random
    import re

    _CYRILLIC_MAP = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }

    def to_latin(s: str) -> str:
        result = []
        for ch in s.lower():
            if ch in _CYRILLIC_MAP:
                result.append(_CYRILLIC_MAP[ch])
            else:
                result.append(ch)
        return ''.join(result)

    fn = re.sub(r'[^a-z0-9]', '', to_latin(first_name.strip()))
    ln = re.sub(r'[^a-z0-9]', '', to_latin(last_name.strip())) if last_name else ''

    candidates = []
    if fn and ln:
        candidates += [
            f"{fn}_{ln}",
            f"{fn}{ln}",
            f"{fn[0]}{ln}",
            f"{fn}{ln[0]}",
            f"{fn}_{ln[0]}",
            f"{fn[0]}_{ln}",
            f"{ln}_{fn}",
            f"{ln}{fn[0]}",
        ]
        for suffix in [random.randint(1, 99), random.randint(100, 999)]:
            candidates += [
                f"{fn}_{ln}{suffix}",
                f"{fn[0]}{ln}{suffix}",
                f"{fn}{ln[0]}{suffix}",
            ]
    elif fn:
        candidates += [fn]
        for suffix in [random.randint(1, 99), random.randint(100, 999)]:
            candidates.append(f"{fn}{suffix}")

    # Filter: Telegram usernames must be 5-32 chars, a-z0-9_
    valid = []
    seen = set()
    for c in candidates:
        c = re.sub(r'[^a-z0-9_]', '', c)
        if len(c) >= 5 and len(c) <= 32 and c not in seen:
            seen.add(c)
            valid.append(c)
    return valid


@router.post("/accounts/{account_id}/suggest-usernames")
async def suggest_usernames(
    account_id: int,
    first_name: str = Query(...),
    last_name: str = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Generate human-like usernames and check availability."""
    account, proxy = await _get_account_with_proxy(account_id, session)
    if not telegram_engine.session_file_exists(account.phone):
        raise HTTPException(400, "No session file")

    candidates = _generate_username_candidates(first_name, last_name)
    if not candidates:
        return {"suggestions": []}

    kwargs = _account_connect_kwargs(account, proxy)
    try:
        await telegram_engine.connect(account_id, **kwargs)
    except Exception as e:
        raise HTTPException(502, f"Cannot connect to Telegram: {e}")

    try:
        suggestions = []
        for uname in candidates:
            result = await telegram_engine.check_username(account_id, uname)
            if result.get("available"):
                suggestions.append(uname)
                if len(suggestions) >= 5:
                    break
    finally:
        await telegram_engine.disconnect(account_id)
    return {"suggestions": suggestions}


# ═══════════════════════════════════════════════════════════════════════
# AUTO-REPLY CONFIG & CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════

from app.models.telegram_outreach import TgAutoReplyConfig, TgConversation


@router.get("/campaigns/{campaign_id}/auto-reply/config")
async def get_auto_reply_config(campaign_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgAutoReplyConfig).where(TgAutoReplyConfig.campaign_id == campaign_id)
    )
    config = result.scalar()
    if not config:
        return {"enabled": False, "system_prompt": "", "stop_phrases": [], "max_replies_per_conversation": 5,
                "dialog_timeout_hours": 24, "simulate_human": True}
    return {
        "id": config.id, "enabled": config.enabled, "system_prompt": config.system_prompt,
        "stop_phrases": config.stop_phrases or [], "max_replies_per_conversation": config.max_replies_per_conversation,
        "dialog_timeout_hours": config.dialog_timeout_hours, "simulate_human": config.simulate_human,
    }


@router.put("/campaigns/{campaign_id}/auto-reply/config")
async def update_auto_reply_config(campaign_id: int, body: dict, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgAutoReplyConfig).where(TgAutoReplyConfig.campaign_id == campaign_id)
    )
    config = result.scalar()
    if not config:
        config = TgAutoReplyConfig(campaign_id=campaign_id)
        session.add(config)
        await session.flush()

    for key in ["enabled", "system_prompt", "stop_phrases", "max_replies_per_conversation",
                "dialog_timeout_hours", "simulate_human"]:
        if key in body:
            setattr(config, key, body[key])

    return {"ok": True}


@router.get("/campaigns/{campaign_id}/conversations")
async def list_conversations(campaign_id: int, session: AsyncSession = Depends(get_session)):
    from sqlalchemy.orm import joinedload
    result = await session.execute(
        select(TgConversation)
        .where(TgConversation.campaign_id == campaign_id)
        .options(joinedload(TgConversation.recipient), joinedload(TgConversation.account))
        .order_by(TgConversation.last_message_at.desc().nullslast())
    )
    convs = result.scalars().unique().all()
    return [{
        "id": c.id, "status": c.status, "replies_sent": c.replies_sent,
        "recipient_username": c.recipient.username if c.recipient else None,
        "account_phone": c.account.phone if c.account else None,
        "messages": c.messages or [],
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "started_at": c.started_at.isoformat() if c.started_at else None,
    } for c in convs]


@router.post("/campaigns/{campaign_id}/conversations/{conv_id}/stop")
async def stop_conversation(campaign_id: int, conv_id: int, session: AsyncSession = Depends(get_session)):
    conv = await session.get(TgConversation, conv_id)
    if not conv or conv.campaign_id != campaign_id:
        raise HTTPException(404, "Conversation not found")
    conv.status = "stopped"
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# CAMPAIGN REPORTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/report")
async def download_campaign_report(
    campaign_id: int,
    format: str = Query("txt", description="txt or html"),
    session: AsyncSession = Depends(get_session),
):
    """Generate a campaign report in TXT or HTML format."""
    from fastapi.responses import Response
    from sqlalchemy.orm import joinedload

    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Get all messages
    msg_result = await session.execute(
        select(TgOutreachMessage)
        .where(TgOutreachMessage.campaign_id == campaign_id)
        .options(joinedload(TgOutreachMessage.recipient), joinedload(TgOutreachMessage.account))
        .order_by(TgOutreachMessage.sent_at)
    )
    messages = msg_result.scalars().unique().all()

    # Get stats
    stats_result = await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )
    total_recipients = stats_result.scalar() or 0

    sent_count = sum(1 for m in messages if m.status.value == "sent")
    failed_count = sum(1 for m in messages if m.status.value == "failed")
    spam_count = sum(1 for m in messages if m.status.value == "spamblocked")

    if format == "html":
        rows_html = ""
        for m in messages:
            status_color = "#35ad5f" if m.status.value == "sent" else "#d9534f"
            rows_html += f"""<tr>
                <td style="padding:6px;border-bottom:1px solid #eee;font-size:12px">{m.sent_at.strftime('%d.%m.%Y %H:%M:%S') if m.sent_at else ''}</td>
                <td style="padding:6px;border-bottom:1px solid #eee;font-size:12px;font-family:monospace">{m.account.phone if m.account else ''}</td>
                <td style="padding:6px;border-bottom:1px solid #eee;font-size:12px">@{m.recipient.username if m.recipient else ''}</td>
                <td style="padding:6px;border-bottom:1px solid #eee"><span style="color:{status_color};font-weight:bold;font-size:12px">{m.status.value}</span></td>
                <td style="padding:6px;border-bottom:1px solid #eee;font-size:11px;max-width:400px;overflow:hidden;text-overflow:ellipsis">{(m.rendered_text or '')[:120]}</td>
            </tr>"""

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Campaign Report: {campaign.name}</title></head>
        <body style="font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:20px">
        <h1 style="color:#4F46E5">Campaign Report: {campaign.name}</h1>
        <div style="display:flex;gap:20px;margin:20px 0">
            <div style="background:#f0f9ff;padding:15px 25px;border-radius:8px;text-align:center"><div style="font-size:28px;font-weight:bold;color:#4F46E5">{total_recipients}</div><div style="font-size:12px;color:#666">Recipients</div></div>
            <div style="background:#f0fdf4;padding:15px 25px;border-radius:8px;text-align:center"><div style="font-size:28px;font-weight:bold;color:#35ad5f">{sent_count}</div><div style="font-size:12px;color:#666">Sent</div></div>
            <div style="background:#fef2f2;padding:15px 25px;border-radius:8px;text-align:center"><div style="font-size:28px;font-weight:bold;color:#d9534f">{failed_count}</div><div style="font-size:12px;color:#666">Failed</div></div>
            <div style="background:#fffbeb;padding:15px 25px;border-radius:8px;text-align:center"><div style="font-size:28px;font-weight:bold;color:#E5A54B">{spam_count}</div><div style="font-size:12px;color:#666">Spamblocked</div></div>
        </div>
        <table style="width:100%;border-collapse:collapse;margin-top:20px">
            <thead><tr style="background:#f8fafc">
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e2e8f0;font-size:12px">Time</th>
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e2e8f0;font-size:12px">Account</th>
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e2e8f0;font-size:12px">Recipient</th>
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e2e8f0;font-size:12px">Status</th>
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e2e8f0;font-size:12px">Message</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p style="margin-top:30px;color:#999;font-size:11px">Generated by Magnum Opus Telegram Outreach</p>
        </body></html>"""

        return Response(content=html, media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="report_{campaign.name}.html"'})

    else:  # txt
        lines = [
            f"Campaign Report: {campaign.name}",
            f"Status: {campaign.status.value}",
            f"Total Recipients: {total_recipients}",
            f"Messages Sent: {sent_count}",
            f"Failed: {failed_count}",
            f"Spamblocked: {spam_count}",
            "",
            "=" * 80,
            "",
        ]
        for m in messages:
            ts = m.sent_at.strftime('%d.%m.%Y %H:%M:%S') if m.sent_at else '??'
            phone = m.account.phone if m.account else '??'
            username = m.recipient.username if m.recipient else '??'
            text = (m.rendered_text or '').replace('\n', '\\n')[:100]
            status = m.status.value
            err = f" ({m.error_message})" if m.error_message else ""
            lines.append(f"[{ts}] {phone} -> @{username} [{status}{err}] {text}")

        lines.extend(["", "=" * 80, f"Total sent: {sent_count}", f"Failed: {failed_count}", f"Spamblocked: {spam_count}"])
        txt = "\n".join(lines)

        return Response(content=txt, media_type="text/plain",
                        headers={"Content-Disposition": f'attachment; filename="report_{campaign.name}.txt"'})


# ═══════════════════════════════════════════════════════════════════════
# CAMPAIGN ACTIVITY LOG
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/activity")
async def get_campaign_activity(campaign_id: int, limit: int = Query(50, ge=1, le=200),
                                 session: AsyncSession = Depends(get_session)):
    """Get recent activity for a campaign: sent messages + replies, merged and sorted by time."""
    from sqlalchemy.orm import joinedload

    # Recent sent messages
    msg_result = await session.execute(
        select(TgOutreachMessage)
        .where(TgOutreachMessage.campaign_id == campaign_id)
        .options(joinedload(TgOutreachMessage.recipient), joinedload(TgOutreachMessage.account))
        .order_by(desc(TgOutreachMessage.sent_at))
        .limit(limit)
    )
    msgs = msg_result.scalars().unique().all()

    # Recent replies
    reply_result = await session.execute(
        select(TgIncomingReply)
        .where(TgIncomingReply.campaign_id == campaign_id)
        .options(joinedload(TgIncomingReply.recipient), joinedload(TgIncomingReply.account))
        .order_by(desc(TgIncomingReply.received_at))
        .limit(limit)
    )
    replies = reply_result.scalars().unique().all()

    # Merge into unified log
    activity = []
    for m in msgs:
        activity.append({
            "type": "sent",
            "time": m.sent_at.isoformat() if m.sent_at else None,
            "account_phone": m.account.phone if m.account else None,
            "recipient_username": m.recipient.username if m.recipient else None,
            "status": m.status.value,
            "text": (m.rendered_text or "")[:120],
            "error": m.error_message,
        })
    for r in replies:
        activity.append({
            "type": "reply",
            "time": r.received_at.isoformat() if r.received_at else None,
            "account_phone": r.account.phone if r.account else None,
            "recipient_username": r.recipient.username if r.recipient else None,
            "status": "replied",
            "text": (r.message_text or "")[:120],
            "error": None,
        })

    # Sort by time desc
    activity.sort(key=lambda x: x.get("time") or "", reverse=True)
    return {"activity": activity[:limit]}


@router.get("/campaigns/{campaign_id}/daily-stats")
async def get_campaign_daily_stats(campaign_id: int, session: AsyncSession = Depends(get_session)):
    """Accurate daily stats for campaign chart — SQL GROUP BY, no row limit."""
    from sqlalchemy import cast, Date

    # Daily sent/failed from outreach messages
    msg_q = await session.execute(
        select(
            cast(TgOutreachMessage.sent_at, Date).label("day"),
            TgOutreachMessage.status,
            func.count(TgOutreachMessage.id),
        ).where(
            TgOutreachMessage.campaign_id == campaign_id,
        ).group_by("day", TgOutreachMessage.status).order_by("day")
    )
    daily: dict = {}
    for day, status, cnt in msg_q.all():
        ds = day.isoformat()
        if ds not in daily:
            daily[ds] = {"date": ds, "sent": 0, "replied": 0, "failed": 0}
        st = status.value if hasattr(status, "value") else status
        if st == "sent":
            daily[ds]["sent"] += cnt
        elif st in ("failed", "spamblocked"):
            daily[ds]["failed"] += cnt

    # Daily replies from incoming replies
    reply_q = await session.execute(
        select(
            cast(TgIncomingReply.received_at, Date).label("day"),
            func.count(TgIncomingReply.id),
        ).where(
            TgIncomingReply.campaign_id == campaign_id,
        ).group_by("day").order_by("day")
    )
    for day, cnt in reply_q.all():
        ds = day.isoformat()
        if ds not in daily:
            daily[ds] = {"date": ds, "sent": 0, "replied": 0, "failed": 0}
        daily[ds]["replied"] = cnt

    return {"daily_stats": sorted(daily.values(), key=lambda x: x["date"])}


# ═══════════════════════════════════════════════════════════════════════
# INCOMING REPLIES (Phase 6)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/replies", response_model=TgIncomingReplyListResponse)
async def list_campaign_replies(
    campaign_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy.orm import joinedload

    query = (
        select(TgIncomingReply)
        .where(TgIncomingReply.campaign_id == campaign_id)
        .options(joinedload(TgIncomingReply.recipient), joinedload(TgIncomingReply.account))
        .order_by(desc(TgIncomingReply.received_at))
    )
    count_q = select(func.count(TgIncomingReply.id)).where(TgIncomingReply.campaign_id == campaign_id)
    total = (await session.execute(count_q)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    replies = result.scalars().unique().all()

    items = []
    for r in replies:
        items.append(TgIncomingReplyResponse(
            id=r.id, campaign_id=r.campaign_id,
            recipient_id=r.recipient_id,
            recipient_username=r.recipient.username if r.recipient else None,
            account_id=r.account_id,
            account_phone=r.account.phone if r.account else None,
            tg_message_id=r.tg_message_id,
            message_text=r.message_text,
            received_at=r.received_at,
        ))
    return TgIncomingReplyListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/replies/recent", response_model=TgIncomingReplyListResponse)
async def list_recent_replies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """All replies across all campaigns, newest first."""
    from sqlalchemy.orm import joinedload

    query = (
        select(TgIncomingReply)
        .options(joinedload(TgIncomingReply.recipient), joinedload(TgIncomingReply.account))
        .order_by(desc(TgIncomingReply.received_at))
    )
    count_q = select(func.count(TgIncomingReply.id))
    total = (await session.execute(count_q)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    replies = result.scalars().unique().all()

    items = []
    for r in replies:
        items.append(TgIncomingReplyResponse(
            id=r.id, campaign_id=r.campaign_id,
            recipient_id=r.recipient_id,
            recipient_username=r.recipient.username if r.recipient else None,
            account_id=r.account_id,
            account_phone=r.account.phone if r.account else None,
            tg_message_id=r.tg_message_id,
            message_text=r.message_text,
            received_at=r.received_at,
        ))
    return TgIncomingReplyListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/campaigns/{campaign_id}/replies/export")
async def export_campaign_replies(campaign_id: int, session: AsyncSession = Depends(get_session)):
    """Export replies as JSON array."""
    from sqlalchemy.orm import joinedload

    result = await session.execute(
        select(TgIncomingReply)
        .where(TgIncomingReply.campaign_id == campaign_id)
        .options(joinedload(TgIncomingReply.recipient), joinedload(TgIncomingReply.account))
        .order_by(TgIncomingReply.received_at)
    )
    replies = result.scalars().unique().all()
    return [
        {
            "recipient_username": r.recipient.username if r.recipient else None,
            "account_phone": r.account.phone if r.account else None,
            "message": r.message_text,
            "received_at": r.received_at.isoformat() if r.received_at else None,
        }
        for r in replies
    ]


# ═══════════════════════════════════════════════════════════════════════
# CRM — Unified Contacts
# ═══════════════════════════════════════════════════════════════════════

from app.models.telegram_outreach import TgContact, TgContactStatus
import json as _json


def _parse_notes(raw) -> list:
    """Parse notes field — supports both plain text and JSON array."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except (ValueError, TypeError):
        pass
    # Legacy plain text — wrap as single note
    return [{"id": 1, "text": raw, "created_at": "", "author": "system"}] if raw.strip() else []


@router.post("/crm/contacts/{contact_id}/notes")
async def add_crm_contact_note(contact_id: int, body: dict, session: AsyncSession = Depends(get_session)):
    """Add a note to a CRM contact."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Note text required")
    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    existing = _parse_notes(contact.notes)
    new_id = max((n.get("id", 0) for n in existing), default=0) + 1
    note = {"id": new_id, "text": text, "created_at": datetime.utcnow().isoformat(), "author": "user"}
    existing.insert(0, note)
    contact.notes = _json.dumps(existing)
    await session.commit()
    return note


@router.get("/crm/contacts")
async def list_crm_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    search: Optional[str] = None,
    campaign_id: Optional[int] = None,
    exclude_campaign_id: Optional[int] = None,
    project_id: Optional[int] = None,
    cf_field_id: Optional[int] = None,
    cf_value: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(TgContact)
    count_query = select(func.count(TgContact.id))

    if project_id is not None:
        query = query.join(TgCampaign, TgContact.source_campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)
        count_query = count_query.join(TgCampaign, TgContact.source_campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)

    if status:
        query = query.where(TgContact.status == status)
        count_query = count_query.where(TgContact.status == status)
    if search:
        like = f"%{search}%"
        query = query.where(
            (TgContact.username.ilike(like)) | (TgContact.first_name.ilike(like)) |
            (TgContact.last_name.ilike(like)) | (TgContact.company_name.ilike(like))
        )
        count_query = count_query.where(
            (TgContact.username.ilike(like)) | (TgContact.first_name.ilike(like)) |
            (TgContact.last_name.ilike(like)) | (TgContact.company_name.ilike(like))
        )
    if exclude_campaign_id:
        already_in = select(TgRecipient.username).where(TgRecipient.campaign_id == exclude_campaign_id)
        query = query.where(~TgContact.username.in_(already_in))
        count_query = count_query.where(~TgContact.username.in_(already_in))

    # Custom field filter
    if cf_field_id is not None and cf_value is not None:
        cf_sub = select(TgCrmLeadFieldValue.lead_id).where(
            TgCrmLeadFieldValue.field_id == cf_field_id,
            TgCrmLeadFieldValue.value.ilike(f"%{cf_value}%"),
        )
        query = query.where(TgContact.id.in_(cf_sub))
        count_query = count_query.where(TgContact.id.in_(cf_sub))

    total = (await session.execute(count_query)).scalar() or 0
    query = query.order_by(desc(TgContact.last_contacted_at).nullslast()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    contacts = result.scalars().all()

    return {
        "items": [{
            "id": c.id, "username": c.username, "first_name": c.first_name, "last_name": c.last_name,
            "company_name": c.company_name, "status": c.status.value, "tags": c.tags or [],
            "notes": (c.notes or "")[:100], "campaigns": c.campaigns or [],
            "total_messages_sent": c.total_messages_sent, "total_replies_received": c.total_replies_received,
            "first_contacted_at": c.first_contacted_at.isoformat() if c.first_contacted_at else None,
            "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
            "last_reply_at": c.last_reply_at.isoformat() if c.last_reply_at else None,
        } for c in contacts],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/crm/contacts/{contact_id}")
async def get_crm_contact(contact_id: int, session: AsyncSession = Depends(get_session)):
    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    return {
        "id": contact.id, "username": contact.username, "first_name": contact.first_name,
        "last_name": contact.last_name, "company_name": contact.company_name, "phone": contact.phone,
        "status": contact.status.value, "tags": contact.tags or [], "notes": _parse_notes(contact.notes),
        "custom_data": contact.custom_data or {}, "campaigns": contact.campaigns or [],
        "total_messages_sent": contact.total_messages_sent, "total_replies_received": contact.total_replies_received,
        "first_contacted_at": contact.first_contacted_at.isoformat() if contact.first_contacted_at else None,
        "last_contacted_at": contact.last_contacted_at.isoformat() if contact.last_contacted_at else None,
        "last_reply_at": contact.last_reply_at.isoformat() if contact.last_reply_at else None,
    }


@router.put("/crm/contacts/{contact_id}")
async def update_crm_contact(contact_id: int, body: dict, session: AsyncSession = Depends(get_session)):
    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    for key in ["status", "notes", "tags", "first_name", "last_name", "company_name", "phone"]:
        if key in body:
            if key == "status":
                setattr(contact, key, TgContactStatus(body[key]))
            else:
                setattr(contact, key, body[key])
    return {"ok": True}


@router.post("/crm/contacts/bulk-update-status")
async def bulk_update_crm_status(
    contact_ids: list[int],
    status: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    for cid in contact_ids:
        contact = await session.get(TgContact, cid)
        if contact:
            contact.status = TgContactStatus(status)
    return {"ok": True, "count": len(contact_ids)}


@router.delete("/crm/contacts/{contact_id}")
async def delete_crm_contact(contact_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a CRM contact."""
    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    await session.delete(contact)
    await session.commit()
    return {"ok": True}


@router.post("/crm/contacts/bulk-delete")
async def bulk_delete_crm_contacts(body: dict, session: AsyncSession = Depends(get_session)):
    """Delete multiple CRM contacts."""
    ids = body.get("ids", [])
    deleted = 0
    for cid in ids:
        contact = await session.get(TgContact, cid)
        if contact:
            await session.delete(contact)
            deleted += 1
    await session.commit()
    return {"ok": True, "deleted": deleted}


@router.get("/crm/stats")
async def crm_pipeline_stats(
    project_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Pipeline stats for CRM dashboard."""
    stats = {}
    for st in TgContactStatus:
        q = select(func.count(TgContact.id)).where(TgContact.status == st)
        if project_id is not None:
            q = q.join(TgCampaign, TgContact.source_campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)
        count = (await session.execute(q)).scalar() or 0
        stats[st.value] = count
    total = sum(stats.values())
    return {"total": total, **stats}


@router.get("/crm/pipeline")
async def crm_pipeline(
    search: Optional[str] = None,
    project_id: Optional[int] = None,
    limit_per_status: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Pipeline Kanban view — contacts grouped by status with counts."""
    result = {}
    for st in TgContactStatus:
        query = select(TgContact).where(TgContact.status == st)
        count_query = select(func.count(TgContact.id)).where(TgContact.status == st)

        if project_id is not None:
            query = query.join(TgCampaign, TgContact.source_campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)
            count_query = count_query.join(TgCampaign, TgContact.source_campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)

        if search:
            like = f"%{search}%"
            sf = (
                (TgContact.username.ilike(like)) | (TgContact.first_name.ilike(like)) |
                (TgContact.last_name.ilike(like)) | (TgContact.company_name.ilike(like))
            )
            query = query.where(sf)
            count_query = count_query.where(sf)

        total = (await session.execute(count_query)).scalar() or 0
        query = query.order_by(desc(TgContact.last_contacted_at).nullslast()).limit(limit_per_status)
        contacts = (await session.execute(query)).scalars().all()

        result[st.value] = {
            "count": total,
            "contacts": [{
                "id": c.id, "username": c.username, "first_name": c.first_name,
                "last_name": c.last_name, "company_name": c.company_name,
                "status": c.status.value, "tags": c.tags or [],
                "total_messages_sent": c.total_messages_sent,
                "total_replies_received": c.total_replies_received,
                "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
                "campaigns": c.campaigns or [],
            } for c in contacts],
        }
    return result


@router.get("/crm/contacts/{contact_id}/history")
async def get_contact_history(contact_id: int, session: AsyncSession = Depends(get_session)):
    """Get full message history for a CRM contact."""
    from sqlalchemy.orm import joinedload

    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")

    # Find all recipients with this username across campaigns
    recip_result = await session.execute(
        select(TgRecipient).where(TgRecipient.username == contact.username)
    )
    recipient_ids = [r.id for r in recip_result.scalars().all()]

    if not recipient_ids:
        return {"sent": [], "replies": []}

    # Get sent messages
    msgs = await session.execute(
        select(TgOutreachMessage)
        .where(TgOutreachMessage.recipient_id.in_(recipient_ids))
        .options(joinedload(TgOutreachMessage.account))
        .order_by(TgOutreachMessage.sent_at)
    )
    sent = [{
        "type": "sent", "text": m.rendered_text, "status": m.status.value,
        "account_phone": m.account.phone if m.account else None,
        "time": m.sent_at.isoformat() if m.sent_at else None,
    } for m in msgs.scalars().unique().all()]

    # Get replies
    replies = await session.execute(
        select(TgIncomingReply)
        .where(TgIncomingReply.recipient_id.in_(recipient_ids))
        .order_by(TgIncomingReply.received_at)
    )
    received = [{
        "type": "reply", "text": r.message_text,
        "time": r.received_at.isoformat() if r.received_at else None,
    } for r in replies.scalars().all()]

    # Merge and sort
    history = sorted(sent + received, key=lambda x: x.get("time") or "")
    return {"history": history}


@router.get("/crm/contacts/{contact_id}/campaigns")
async def get_contact_campaigns(contact_id: int, session: AsyncSession = Depends(get_session)):
    """Get campaign step progression for a CRM contact."""
    from sqlalchemy.orm import joinedload, selectinload

    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")

    # Find all recipients with this username, load campaign + sequence
    recip_result = await session.execute(
        select(TgRecipient)
        .where(TgRecipient.username == contact.username)
        .options(
            joinedload(TgRecipient.campaign).selectinload(TgCampaign.sequence).selectinload(TgSequence.steps),
        )
    )
    recipients = recip_result.scalars().unique().all()

    if not recipients:
        return {"campaigns": []}

    # Get all outreach messages for these recipients
    msg_result = await session.execute(
        select(TgOutreachMessage)
        .where(TgOutreachMessage.recipient_id.in_([r.id for r in recipients]))
        .order_by(TgOutreachMessage.sent_at)
    )
    all_msgs = msg_result.scalars().all()
    msgs_by_recipient: dict[int, list] = {}
    for m in all_msgs:
        msgs_by_recipient.setdefault(m.recipient_id, []).append(m)

    campaigns = []
    for recip in recipients:
        camp = recip.campaign
        if not camp:
            continue
        seq = camp.sequence
        total_steps = len(seq.steps) if seq else 0

        # Build per-step info
        recip_msgs = msgs_by_recipient.get(recip.id, [])
        steps_info = []
        for step in (seq.steps if seq else []):
            step_msg = next((m for m in recip_msgs if m.step_id == step.id), None)
            steps_info.append({
                "step_order": step.step_order,
                "delay_days": step.delay_days,
                "label": "Initial" if step.step_order == 1 else f"Follow-up {step.step_order - 1}",
                "status": step_msg.status.value if step_msg else ("scheduled" if step.step_order == recip.current_step + 1 else "pending"),
                "sent_at": step_msg.sent_at.isoformat() if step_msg and step_msg.sent_at else None,
                "read_at": step_msg.read_at.isoformat() if step_msg and step_msg.read_at else None,
            })

        campaigns.append({
            "campaign_id": camp.id,
            "campaign_name": camp.name,
            "campaign_status": camp.status.value,
            "recipient_status": recip.status.value,
            "current_step": recip.current_step,
            "total_steps": total_steps,
            "steps": steps_info,
        })

    return {"campaigns": campaigns}


# ═══════════════════════════════════════════════════════════════════════
# CRM — Custom Fields (Custom Properties)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/crm/custom-fields", response_model=list[TgCrmCustomFieldResponse])
async def list_custom_fields(
    project_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """List all custom field definitions."""
    q = select(TgCrmCustomField).order_by(TgCrmCustomField.sort_order, TgCrmCustomField.id)
    if project_id is not None:
        q = q.where(TgCrmCustomField.project_id == project_id)
    else:
        q = q.where(TgCrmCustomField.project_id.is_(None))
    result = await session.execute(q)
    return result.scalars().all()


@router.post("/crm/custom-fields", response_model=TgCrmCustomFieldResponse)
async def create_custom_field(
    body: TgCrmCustomFieldCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new custom field definition."""
    TgCrmCustomFieldType(body.field_type)  # validate enum
    field = TgCrmCustomField(
        name=body.name,
        field_type=TgCrmCustomFieldType(body.field_type),
        options_json=body.options_json,
        project_id=body.project_id,
        sort_order=body.sort_order,
    )
    session.add(field)
    await session.flush()
    await session.refresh(field)
    return field


@router.put("/crm/custom-fields/{field_id}", response_model=TgCrmCustomFieldResponse)
async def update_custom_field(
    field_id: int,
    body: TgCrmCustomFieldUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a custom field definition."""
    field = await session.get(TgCrmCustomField, field_id)
    if not field:
        raise HTTPException(404, "Custom field not found")
    if body.name is not None:
        field.name = body.name
    if body.field_type is not None:
        field.field_type = TgCrmCustomFieldType(body.field_type)
    if body.options_json is not None:
        field.options_json = body.options_json
    if body.sort_order is not None:
        field.sort_order = body.sort_order
    await session.flush()
    await session.refresh(field)
    return field


@router.delete("/crm/custom-fields/{field_id}")
async def delete_custom_field(
    field_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a custom field and all its values."""
    field = await session.get(TgCrmCustomField, field_id)
    if not field:
        raise HTTPException(404, "Custom field not found")
    await session.delete(field)
    return {"ok": True}


@router.get("/crm/contacts/{contact_id}/custom-fields")
async def get_contact_custom_fields(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all custom field values for a contact."""
    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")

    result = await session.execute(
        select(TgCrmLeadFieldValue, TgCrmCustomField)
        .join(TgCrmCustomField, TgCrmLeadFieldValue.field_id == TgCrmCustomField.id)
        .where(TgCrmLeadFieldValue.lead_id == contact_id)
        .order_by(TgCrmCustomField.sort_order, TgCrmCustomField.id)
    )
    rows = result.all()
    return [
        {
            "id": val.id,
            "lead_id": val.lead_id,
            "field_id": val.field_id,
            "value": val.value,
            "field_name": fld.name,
            "field_type": fld.field_type.value,
            "options_json": fld.options_json or [],
        }
        for val, fld in rows
    ]


@router.put("/crm/contacts/{contact_id}/custom-fields")
async def update_contact_custom_fields(
    contact_id: int,
    values: list[TgCrmLeadFieldValueUpdate],
    session: AsyncSession = Depends(get_session),
):
    """Bulk upsert custom field values for a contact."""
    contact = await session.get(TgContact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")

    for item in values:
        existing = await session.execute(
            select(TgCrmLeadFieldValue).where(
                TgCrmLeadFieldValue.lead_id == contact_id,
                TgCrmLeadFieldValue.field_id == item.field_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.value = item.value
        else:
            session.add(TgCrmLeadFieldValue(
                lead_id=contact_id,
                field_id=item.field_id,
                value=item.value,
            ))

    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# TOOLS — Phone Checker + Story Engagement
# ═══════════════════════════════════════════════════════════════════════

@router.post("/tools/check-phones")
async def check_phone_numbers(
    phones: list[str],
    account_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Check which phone numbers are registered on Telegram."""
    from telethon import functions, types

    account, proxy = await _get_account_with_proxy(account_id, session)
    kwargs = _account_connect_kwargs(account, proxy)
    await telegram_engine.connect(account_id, **kwargs)
    client = telegram_engine.get_client(account_id)
    if not client or not await client.is_user_authorized():
        raise HTTPException(400, "Account not authorized")

    results = []
    for phone in phones:
        phone = phone.strip().lstrip("+")
        if not phone:
            continue
        try:
            contact = types.InputPhoneContact(client_id=0, phone=f"+{phone}", first_name="", last_name="")
            imported = await client(functions.contacts.ImportContactsRequest([contact]))
            if imported.users:
                user = imported.users[0]
                results.append({
                    "phone": phone, "registered": True,
                    "user_id": user.id, "username": user.username,
                    "first_name": user.first_name, "last_name": user.last_name,
                })
                # Clean up imported contact
                try:
                    await client(functions.contacts.DeleteContactsRequest(id=[types.InputUser(user.id, user.access_hash)]))
                except Exception:
                    pass
            else:
                results.append({"phone": phone, "registered": False})
        except Exception as e:
            results.append({"phone": phone, "registered": False, "error": str(e)[:50]})

    await telegram_engine.disconnect(account_id)
    registered = sum(1 for r in results if r.get("registered"))
    return {"total": len(results), "registered": registered, "results": results}


@router.post("/tools/mass-view-stories")
async def mass_view_stories(
    usernames: list[str],
    account_ids: list[int],
    react: bool = Query(False),
    reaction_emoji: str = Query("👍"),
    session: AsyncSession = Depends(get_session),
):
    """Mass-view (and optionally react to) stories of target users."""
    import random

    viewed = 0
    reacted = 0
    errors = []

    for username in usernames:
        username = username.strip().lstrip("@")
        if not username:
            continue
        # Pick random account
        aid = random.choice(account_ids)
        account = await session.get(TgAccount, aid)
        if not account or not account.api_id or not telegram_engine.session_file_exists(account.phone):
            continue

        try:
            kwargs = _account_connect_kwargs(account)
            await telegram_engine.connect(aid, **kwargs)
            client = telegram_engine.get_client(aid)
            if not client or not await client.is_user_authorized():
                continue

            from telethon import functions
            entity = await client.get_entity(username)

            # Get stories
            try:
                stories_result = await client(functions.stories.GetPeerStoriesRequest(peer=entity))
                stories = getattr(stories_result, 'stories', None)
                if stories and hasattr(stories, 'stories'):
                    for story in stories.stories[:3]:  # max 3 per user
                        # Mark as read
                        try:
                            await client(functions.stories.ReadStoriesRequest(
                                peer=entity, max_id=story.id
                            ))
                            viewed += 1
                        except Exception:
                            pass

                        # React
                        if react:
                            try:
                                from telethon.tl.types import ReactionEmoji
                                await client(functions.stories.SendReactionRequest(
                                    peer=entity, story_id=story.id,
                                    reaction=ReactionEmoji(emoticon=reaction_emoji),
                                ))
                                reacted += 1
                            except Exception:
                                pass

                        await asyncio.sleep(random.uniform(1, 3))
            except Exception as e:
                errors.append(f"@{username}: {str(e)[:40]}")

            await telegram_engine.disconnect(aid)
            await asyncio.sleep(random.uniform(2, 5))
        except Exception as e:
            errors.append(f"@{username}: {str(e)[:40]}")

    return {"viewed": viewed, "reacted": reacted, "errors": errors}


# ═══════════════════════════════════════════════════════════════════════
# AUDIENCE PARSER
# ═══════════════════════════════════════════════════════════════════════

@router.post("/parser/scrape-group")
async def scrape_group_members(
    group_username: str = Query(...),
    account_id: int = Query(..., description="Account to use for scraping"),
    has_username: bool = Query(True),
    limit: int = Query(500, ge=1, le=5000),
    session: AsyncSession = Depends(get_session),
):
    """Scrape members from a Telegram group/channel using specified account."""
    account, proxy = await _get_account_with_proxy(account_id, session)
    kwargs = _account_connect_kwargs(account, proxy)
    await telegram_engine.connect(account_id, **kwargs)
    client = telegram_engine.get_client(account_id)
    if not client or not await client.is_user_authorized():
        raise HTTPException(400, "Account not authorized")

    try:
        entity = await client.get_entity(group_username)
        participants = await client.get_participants(entity, limit=limit)

        members = []
        for p in participants:
            if has_username and not p.username:
                continue
            members.append({
                "user_id": p.id,
                "username": p.username,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "is_premium": getattr(p, 'premium', False),
                "has_photo": p.photo is not None,
            })

        await telegram_engine.disconnect(account_id)
        return {"group": group_username, "total_found": len(participants), "filtered": len(members), "members": members}
    except Exception as e:
        await telegram_engine.disconnect(account_id)
        raise HTTPException(400, f"Scraping failed: {e}")


@router.post("/parser/add-to-campaign")
async def add_parsed_to_campaign(
    campaign_id: int = Query(...),
    members: list[dict] = [],
    session: AsyncSession = Depends(get_session),
):
    """Add parsed members as recipients to a campaign."""
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    added = 0
    for m in members:
        username = (m.get("username") or "").strip()
        if not username:
            continue
        existing = await session.execute(
            select(TgRecipient).where(TgRecipient.campaign_id == campaign_id, TgRecipient.username == username)
        )
        if existing.scalar():
            continue
        session.add(TgRecipient(
            campaign_id=campaign_id, username=username,
            first_name=m.get("first_name"), company_name=None,
        ))
        added += 1

    campaign.total_recipients = (await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )).scalar() or 0

    return {"ok": True, "added": added, "total": campaign.total_recipients}


# ═══════════════════════════════════════════════════════════════════════
# ACCOUNT EXPORT & CLEANING
# ═══════════════════════════════════════════════════════════════════════

@router.get("/accounts/export")
async def export_accounts(session: AsyncSession = Depends(get_session)):
    """Export all accounts as CSV."""
    from fastapi.responses import Response
    import csv
    import io

    result = await session.execute(select(TgAccount).order_by(TgAccount.id))
    accounts = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["phone", "username", "first_name", "last_name", "status", "spamblock",
                     "messages_sent_today", "total_messages_sent", "daily_message_limit",
                     "device_model", "system_version", "app_version", "lang_code", "country_code",
                     "last_connected_at", "created_at"])
    for a in accounts:
        writer.writerow([
            a.phone, a.username, a.first_name, a.last_name,
            a.status.value if a.status else "", a.spamblock_type.value if a.spamblock_type else "",
            a.messages_sent_today, a.total_messages_sent, a.daily_message_limit,
            a.device_model, a.system_version, a.app_version, a.lang_code,
            a.country_code, a.last_connected_at, a.created_at,
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="accounts_export.csv"'},
    )


@router.post("/accounts/bulk-clean")
async def bulk_clean_accounts(
    data: TgBulkAccountIds,
    delete_dialogs: bool = Query(False),
    delete_contacts: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Clean up accounts — delete dialogs, contacts via Telethon."""
    from telethon import functions

    cleaned = 0
    errors = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account or not account.api_id or not telegram_engine.session_file_exists(account.phone):
            continue
        try:
            kwargs = _account_connect_kwargs(account)
            await telegram_engine.connect(aid, **kwargs)
            client = telegram_engine.get_client(aid)
            if not client or not await client.is_user_authorized():
                continue

            if delete_dialogs:
                dialogs = await client.get_dialogs(limit=100)
                for d in dialogs:
                    try:
                        await client.delete_dialog(d)
                    except Exception:
                        pass

            if delete_contacts:
                try:
                    contacts = await client(functions.contacts.GetContactsRequest(hash=0))
                    if contacts.contacts:
                        user_ids = [c.user_id for c in contacts.contacts]
                        from telethon import types
                        input_users = []
                        for uid in user_ids:
                            try:
                                input_users.append(await client.get_input_entity(uid))
                            except Exception:
                                pass
                        if input_users:
                            await client(functions.contacts.DeleteContactsRequest(id=input_users))
                except Exception:
                    pass

            await telegram_engine.disconnect(aid)
            cleaned += 1
        except Exception as e:
            errors.append(f"{account.phone}: {str(e)[:50]}")

    return {"ok": True, "cleaned": cleaned, "errors": errors}


# ═══════════════════════════════════════════════════════════════════════
# SENDING WORKER — Management (Phase 5)
# ═══════════════════════════════════════════════════════════════════════

from app.services.sending_worker import sending_worker
from app.services.reply_detector import reply_detector


@router.get("/worker/status")
async def worker_status():
    return {
        "sending": sending_worker.is_running,
        "replies": reply_detector.is_running,
        "running": sending_worker.is_running,  # backwards compat
    }


@router.post("/worker/start")
async def worker_start():
    sending_worker.start()
    reply_detector.start()
    return {"ok": True, "sending": True, "replies": True}


@router.post("/worker/stop")
async def worker_stop():
    sending_worker.stop()
    reply_detector.stop()
    return {"ok": True, "sending": False, "replies": False}


@router.post("/worker/reset-daily-counters")
async def worker_reset_counters():
    await sending_worker.reset_daily_counters()
    return {"ok": True, "message": "Daily counters reset"}


# ═══════════════════════════════════════════════════════════════════════
# INBOX — Threads, Messages, Replies, Tags (Phase 6)
# ═══════════════════════════════════════════════════════════════════════


@router.patch("/campaigns/{campaign_id}/tags")
async def update_campaign_tags(
    campaign_id: int,
    tags: list[str],
    session: AsyncSession = Depends(get_session),
):
    """Update tags on a campaign (full replace)."""
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    campaign.tags = tags
    await session.flush()
    return {"ok": True, "tags": campaign.tags}


@router.get("/inbox/threads")
async def list_inbox_threads(
    campaign_id: Optional[int] = None,
    account_id: Optional[int] = None,
    campaign_tag: Optional[str] = None,
    tag: Optional[str] = None,  # recipient inbox_tag filter
    project_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List inbox threads — recipients who replied, grouped by recipient with latest reply info."""

    # Subquery: per-recipient reply stats (latest reply time + count)
    reply_stats_sq = (
        select(
            TgIncomingReply.recipient_id,
            func.max(TgIncomingReply.received_at).label("last_reply_at"),
            func.count(TgIncomingReply.id).label("reply_count"),
        )
        .group_by(TgIncomingReply.recipient_id)
        .subquery("reply_stats")
    )

    # Main query: recipients joined with campaign + account + reply stats
    query = (
        select(
            TgRecipient,
            TgCampaign.name.label("campaign_name"),
            TgCampaign.tags.label("campaign_tags"),
            TgAccount.id.label("account_id"),
            TgAccount.phone.label("account_phone"),
            TgAccount.username.label("account_username"),
            reply_stats_sq.c.last_reply_at,
            reply_stats_sq.c.reply_count,
        )
        .join(TgCampaign, TgRecipient.campaign_id == TgCampaign.id)
        .join(TgAccount, TgRecipient.assigned_account_id == TgAccount.id)
        .join(reply_stats_sq, TgRecipient.id == reply_stats_sq.c.recipient_id)
        .where(TgRecipient.status == TgRecipientStatus.REPLIED)
    )

    count_query = (
        select(func.count(TgRecipient.id))
        .join(TgCampaign, TgRecipient.campaign_id == TgCampaign.id)
        .join(TgAccount, TgRecipient.assigned_account_id == TgAccount.id)
        .join(reply_stats_sq, TgRecipient.id == reply_stats_sq.c.recipient_id)
        .where(TgRecipient.status == TgRecipientStatus.REPLIED)
    )

    # Filters
    if project_id is not None:
        query = query.where(TgCampaign.project_id == project_id)
        count_query = count_query.where(TgCampaign.project_id == project_id)

    if campaign_id is not None:
        query = query.where(TgRecipient.campaign_id == campaign_id)
        count_query = count_query.where(TgRecipient.campaign_id == campaign_id)

    if account_id is not None:
        query = query.where(TgRecipient.assigned_account_id == account_id)
        count_query = count_query.where(TgRecipient.assigned_account_id == account_id)

    if campaign_tag is not None:
        # JSONB array contains check
        tag_filter = TgCampaign.tags.op("@>")(f'["{campaign_tag}"]')
        query = query.where(tag_filter)
        count_query = count_query.where(tag_filter)

    if tag is not None:
        if tag == "":
            query = query.where(TgRecipient.inbox_tag.is_(None))
            count_query = count_query.where(TgRecipient.inbox_tag.is_(None))
        else:
            query = query.where(TgRecipient.inbox_tag == tag)
            count_query = count_query.where(TgRecipient.inbox_tag == tag)

    total = (await session.execute(count_query)).scalar() or 0

    query = query.order_by(desc(reply_stats_sq.c.last_reply_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    rows = result.all()

    # For each row, fetch the actual latest reply text
    items = []
    for row in rows:
        recip = row[0]  # TgRecipient
        campaign_name = row.campaign_name
        campaign_tags = row.campaign_tags or []
        acct_id = row.account_id
        account_phone = row.account_phone
        account_username = row.account_username
        last_reply_at = row.last_reply_at
        reply_count = row.reply_count or 0

        # Fetch the latest reply text
        last_reply_q = await session.execute(
            select(TgIncomingReply.message_text)
            .where(
                TgIncomingReply.recipient_id == recip.id,
                TgIncomingReply.received_at == last_reply_at,
            )
            .limit(1)
        )
        last_reply_text = last_reply_q.scalar() or ""

        items.append({
            "recipient_id": recip.id,
            "recipient_username": recip.username,
            "first_name": recip.first_name,
            "company_name": recip.company_name,
            "campaign_id": recip.campaign_id,
            "campaign_name": campaign_name,
            "campaign_tags": campaign_tags,
            "account_id": acct_id,
            "account_phone": account_phone,
            "account_username": account_username,
            "last_message_text": last_reply_text[:200],
            "last_message_at": last_reply_at.isoformat() if last_reply_at else None,
            "reply_count": reply_count,
            "tag": recip.inbox_tag,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/inbox/threads/{recipient_id}/messages")
async def get_thread_messages(
    recipient_id: int,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get all messages for a recipient thread — outbound + inbound merged by time."""
    recipient = await session.get(TgRecipient, recipient_id)
    if not recipient:
        raise HTTPException(404, "Recipient not found")

    # Load campaign name
    campaign = await session.get(TgCampaign, recipient.campaign_id)
    campaign_name = campaign.name if campaign else None

    # Load account phone
    account_phone = None
    if recipient.assigned_account_id:
        acct = await session.get(TgAccount, recipient.assigned_account_id)
        account_phone = acct.phone if acct else None

    # Outbound messages
    out_result = await session.execute(
        select(TgOutreachMessage)
        .where(TgOutreachMessage.recipient_id == recipient_id)
        .options(joinedload(TgOutreachMessage.account))
        .order_by(TgOutreachMessage.sent_at)
    )
    outbound = []
    for m in out_result.scalars().unique().all():
        outbound.append({
            "id": m.id,
            "direction": "outbound",
            "text": m.rendered_text,
            "timestamp": m.sent_at.isoformat() if m.sent_at else None,
            "account_id": m.account_id,
            "account_phone": m.account.phone if m.account else None,
            "status": m.status.value if m.status else None,
        })

    # Inbound replies
    in_result = await session.execute(
        select(TgIncomingReply)
        .where(TgIncomingReply.recipient_id == recipient_id)
        .options(joinedload(TgIncomingReply.account))
        .order_by(TgIncomingReply.received_at)
    )
    inbound = []
    for r in in_result.scalars().unique().all():
        inbound.append({
            "id": r.id,
            "direction": "inbound",
            "text": r.message_text,
            "timestamp": r.received_at.isoformat() if r.received_at else None,
            "account_id": r.account_id,
            "account_phone": r.account.phone if r.account else None,
            "status": None,
        })

    # Merge and sort by timestamp, then apply limit
    messages = sorted(outbound + inbound, key=lambda x: x.get("timestamp") or "")
    messages = messages[-limit:]  # keep the most recent N messages

    return {
        "recipient_id": recipient.id,
        "username": recipient.username,
        "first_name": recipient.first_name,
        "campaign_id": recipient.campaign_id,
        "campaign_name": campaign_name,
        "account_phone": account_phone,
        "tag": recipient.inbox_tag,
        "messages": messages,
    }


@router.post("/inbox/threads/{recipient_id}/send")
async def send_inbox_reply(
    recipient_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Send a reply to a recipient from their assigned account (or last-used account)."""
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Message text is required")

    recipient = await session.get(TgRecipient, recipient_id)
    if not recipient:
        raise HTTPException(404, "Recipient not found")

    # Determine which account to send from
    account_id = recipient.assigned_account_id
    if not account_id:
        # Fallback: find the account that sent the last message to this recipient
        last_msg_q = await session.execute(
            select(TgOutreachMessage.account_id)
            .where(TgOutreachMessage.recipient_id == recipient_id)
            .order_by(desc(TgOutreachMessage.sent_at))
            .limit(1)
        )
        account_id = last_msg_q.scalar()

    if not account_id:
        raise HTTPException(400, "No account found for this recipient (no assigned account and no previous messages)")

    account, proxy = await _get_account_with_proxy(account_id, session)

    if account.status != TgAccountStatus.ACTIVE:
        raise HTTPException(400, f"Account {account.phone} is not active (status: {account.status.value})")

    if not telegram_engine.session_file_exists(account.phone):
        raise HTTPException(400, f"No session file for account {account.phone}")

    kwargs = _account_connect_kwargs(account, proxy)
    try:
        await telegram_engine.connect(account.id, **kwargs)
        result = await telegram_engine.send_message(
            account.id,
            recipient.username,
            text,
        )

        if result.get("status") == "ok":
            # Log the outbound message (step_id=None, variant_id=None for manual sends)
            msg = TgOutreachMessage(
                campaign_id=recipient.campaign_id,
                recipient_id=recipient.id,
                account_id=account.id,
                step_id=None,
                variant_id=None,
                rendered_text=text,
                status=TgMessageStatus.SENT,
            )
            session.add(msg)
            await session.flush()

        await telegram_engine.disconnect(account.id)
        return {"ok": result.get("status") == "ok", "detail": result}

    except Exception as e:
        try:
            await telegram_engine.disconnect(account.id)
        except Exception:
            pass
        raise HTTPException(500, f"Failed to send reply: {e}")


@router.patch("/inbox/threads/{recipient_id}/tag")
async def tag_inbox_thread(
    recipient_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Set inbox tag on a recipient. Valid: interested, info_requested, not_interested, or empty to clear."""
    tag = body.get("tag", "")
    valid_tags = {"interested", "info_requested", "not_interested", ""}
    if tag not in valid_tags:
        raise HTTPException(400, f"Invalid tag. Must be one of: {', '.join(valid_tags)}")

    recipient = await session.get(TgRecipient, recipient_id)
    if not recipient:
        raise HTTPException(404, "Recipient not found")

    recipient.inbox_tag = tag if tag else None
    # Also store in custom_variables for backward compat
    if recipient.custom_variables is None:
        recipient.custom_variables = {}
    cv = dict(recipient.custom_variables)
    cv["inbox_tag"] = tag if tag else None
    recipient.custom_variables = cv
    await session.flush()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# UNIFIED INBOX — Dialog-based (TgInboxDialog cache)
# ═══════════════════════════════════════════════════════════════════════

from datetime import datetime
from app.services.inbox_sync_service import inbox_sync_service
from app.services.telegram_dm_service import telegram_dm_service
from app.models.telegram_dm import TelegramDMAccount


@router.get("/inbox/accounts")
async def list_inbox_accounts(session: AsyncSession = Depends(get_session)):
    """List telegram_dm_accounts available for inbox (active sessions only)."""
    result = await session.execute(
        select(TelegramDMAccount).where(
            TelegramDMAccount.string_session.isnot(None),
            TelegramDMAccount.auth_status == "active",
        ).order_by(TelegramDMAccount.id)
    )
    dm_accounts = result.scalars().all()

    # Batch-load matching TgAccounts to get campaign/tag info & filter deleted
    phones = [a.phone for a in dm_accounts if a.phone]
    tg_map: dict = {}
    if phones:
        tg_result = await session.execute(
            select(TgAccount)
            .where(TgAccount.phone.in_(phones))
            .options(selectinload(TgAccount.campaign_links), selectinload(TgAccount.tags))
        )
        for tg in tg_result.scalars().all():
            tg_map[tg.phone] = tg

    response = []
    for a in dm_accounts:
        tg = tg_map.get(a.phone)
        # Skip accounts whose TgAccount was deleted or is dead/banned
        if not tg:
            continue
        if tg.status in (TgAccountStatus.DEAD, TgAccountStatus.BANNED):
            continue
        campaign_ids = [cl.campaign_id for cl in tg.campaign_links] if tg else []
        tag_names = [t.name for t in tg.tags] if tg else []
        response.append({
            "id": a.id,
            "phone": a.phone,
            "username": a.username,
            "first_name": a.first_name,
            "last_name": a.last_name,
            "is_connected": a.is_connected,
            "auth_status": a.auth_status,
            "tg_status": tg.status.value if tg else None,
            "campaign_ids": campaign_ids,
            "tag_names": tag_names,
        })
    return response


@router.get("/inbox/dialogs")
async def list_inbox_dialogs(
    account_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    campaign_tag: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    lead_status: Optional[str] = None,
    unread_only: bool = False,
    replied: Optional[str] = None,  # "replied" | "not_replied"
    project_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List cached dialogs. At least one filter required."""
    has_any_filter = account_id or campaign_id or campaign_tag or tag or lead_status or unread_only or replied or project_id
    if not has_any_filter:
        raise HTTPException(400, "Select at least one filter")

    query = select(TgInboxDialog).order_by(TgInboxDialog.last_message_at.desc().nullslast())
    count_q = select(func.count(TgInboxDialog.id))

    if account_id:
        # Dialogs are stored with DM account IDs (from inbox_sync_service).
        # Also include TG outreach account IDs (via phone) for backwards compat.
        all_ids = [account_id]
        dm_acc = await session.get(TelegramDMAccount, account_id)
        if dm_acc and dm_acc.phone:
            tg_accs = (await session.execute(
                select(TgAccount.id).where(TgAccount.phone == dm_acc.phone)
            )).scalars().all()
            all_ids.extend(tg_accs)
        query = query.where(TgInboxDialog.account_id.in_(all_ids))
        count_q = count_q.where(TgInboxDialog.account_id.in_(all_ids))
    if campaign_id:
        query = query.where(TgInboxDialog.campaign_id == campaign_id)
        count_q = count_q.where(TgInboxDialog.campaign_id == campaign_id)
    if campaign_tag:
        # Join with TgCampaign to filter by tag (JSONB array contains)
        from sqlalchemy import type_coerce
        from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
        tag_json = type_coerce([campaign_tag], PG_JSONB)
        query = query.join(TgCampaign, TgInboxDialog.campaign_id == TgCampaign.id).where(
            TgCampaign.tags.op("@>")(tag_json)
        )
        count_q = count_q.join(TgCampaign, TgInboxDialog.campaign_id == TgCampaign.id).where(
            TgCampaign.tags.op("@>")(tag_json)
        )
    if project_id is not None and not campaign_tag:
        # Join TgCampaign only if not already joined above (via campaign_tag)
        query = query.join(TgCampaign, TgInboxDialog.campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)
        count_q = count_q.join(TgCampaign, TgInboxDialog.campaign_id == TgCampaign.id).where(TgCampaign.project_id == project_id)
    elif project_id is not None and campaign_tag:
        # TgCampaign already joined via campaign_tag filter above
        query = query.where(TgCampaign.project_id == project_id)
        count_q = count_q.where(TgCampaign.project_id == project_id)
    if tag:
        query = query.where(TgInboxDialog.inbox_tag == tag)
        count_q = count_q.where(TgInboxDialog.inbox_tag == tag)
    if search:
        like = f"%{search}%"
        query = query.where(
            (TgInboxDialog.peer_name.ilike(like)) | (TgInboxDialog.peer_username.ilike(like))
        )
        count_q = count_q.where(
            (TgInboxDialog.peer_name.ilike(like)) | (TgInboxDialog.peer_username.ilike(like))
        )
    if unread_only:
        query = query.where(TgInboxDialog.unread_count > 0)
        count_q = count_q.where(TgInboxDialog.unread_count > 0)
    if replied == "replied":
        # Peer replied — last message is inbound (not outbound)
        query = query.where(TgInboxDialog.last_message_outbound == False)
        count_q = count_q.where(TgInboxDialog.last_message_outbound == False)
    elif replied == "not_replied":
        # Peer hasn't replied — last message is outbound or null
        query = query.where((TgInboxDialog.last_message_outbound == True) | (TgInboxDialog.last_message_outbound.is_(None)))
        count_q = count_q.where((TgInboxDialog.last_message_outbound == True) | (TgInboxDialog.last_message_outbound.is_(None)))
    if lead_status:
        # Match CRM contact status OR dialog inbox_tag (set via tag buttons in chat)
        from sqlalchemy import or_, cast
        from sqlalchemy import String as SAString
        # Check if lead_status is a valid CRM enum value before querying
        valid_crm_statuses = {s.value for s in TgContactStatus}
        if lead_status in valid_crm_statuses:
            contact_sub = select(TgContact.username).where(TgContact.status == lead_status).subquery()
            status_filter = or_(
                TgInboxDialog.peer_username.in_(select(contact_sub)),
                TgInboxDialog.inbox_tag == lead_status,
            )
        else:
            # Not a valid CRM status — only match by inbox_tag
            status_filter = TgInboxDialog.inbox_tag == lead_status
        query = query.where(status_filter)
        count_q = count_q.where(status_filter)

    total = (await session.execute(count_q)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    dialogs = result.scalars().all()

    # Get account info: resolve TG outreach account → phone → DM account
    account_cache = {}
    campaign_cache = {}
    items = []
    for d in dialogs:
        if d.account_id not in account_cache:
            # Always resolve via TG outreach account (account_id is tg_accounts.id)
            acc = None
            tg_acc = await session.get(TgAccount, d.account_id)
            if tg_acc and tg_acc.phone:
                dm_r = await session.execute(
                    select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone).limit(1)
                )
                acc = dm_r.scalar()
            if not acc:
                # Fallback: try DM account by ID
                acc = await session.get(TelegramDMAccount, d.account_id)
            account_cache[d.account_id] = acc
        acc = account_cache[d.account_id]

        # Get campaign name
        campaign_name = None
        if d.campaign_id:
            if d.campaign_id not in campaign_cache:
                camp = await session.get(TgCampaign, d.campaign_id)
                campaign_cache[d.campaign_id] = camp.name if camp else None
            campaign_name = campaign_cache[d.campaign_id]

        items.append({
            "id": d.id,
            "account_id": d.account_id,
            "account_phone": acc.phone if acc else None,
            "account_username": acc.username if acc else None,
            "account_name": f"{acc.first_name or ''} {acc.last_name or ''}".strip() if acc else None,
            "peer_id": d.peer_id,
            "peer_name": d.peer_name or "Unknown",
            "peer_username": d.peer_username,
            "last_message_text": d.last_message_text,
            "last_message_at": d.last_message_at.isoformat() if d.last_message_at else None,
            "last_message_outbound": d.last_message_outbound,
            "unread_count": d.unread_count,
            "campaign_id": d.campaign_id,
            "campaign_name": campaign_name,
            "tag": d.inbox_tag,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/inbox/dialogs/{dialog_id}/messages")
async def get_dialog_messages(
    dialog_id: int,
    limit: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Fetch real messages from Telegram for a dialog via telegram_dm_service."""
    from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    # Resolve TG outreach account_id to DM account via phone
    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        raise HTTPException(404, "Outreach account not found")
    dm_result = await session.execute(
        select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone)
    )
    candidates = dm_result.scalars().all()
    # Prefer connected account
    account = None
    for c in candidates:
        if telegram_dm_service.is_connected(c.id) and c.string_session:
            account = c
            break
    if not account:
        for c in candidates:
            if c.string_session:
                account = c
                break
    if not account:
        raise HTTPException(404, "DM account not found for this phone")
    if not account.string_session:
        raise HTTPException(400, "Account has no string_session")

    proxy_cfg = await _resolve_dm_proxy(account, session)

    # Check if already connected — avoid disconnect at the end if so
    already_connected = telegram_dm_service.is_connected(account.id)

    try:
        if not already_connected:
            ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
            if not ok:
                # Retry once for temporary connection failures (network/proxy)
                import asyncio as _aio
                await _aio.sleep(2)
                ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
                if not ok:
                    raise HTTPException(503, "Temporary connection error — please try again")

        messages = await telegram_dm_service.get_messages(account.id, dialog.peer_id, limit=limit)

        # Map field names to match existing frontend expectations
        formatted = []
        for m in messages:
            formatted.append({
                "id": m["id"],
                "direction": m["direction"],
                "text": m.get("text", ""),
                "timestamp": m.get("sent_at"),
                "reply_to": m.get("reply_to"),
                "reactions": m.get("reactions", []),
                "sender_name": m.get("sender_name", ""),
                "is_read": m.get("is_read", False),
                "fwd_from": m.get("fwd_from"),
                "media": m.get("media"),
            })

        # Get peer online status + block detection
        peer_status = {"status": "unknown", "last_seen": None, "possibly_blocked": False}
        try:
            from telethon.tl.types import (
                UserStatusOnline, UserStatusOffline, UserStatusRecently,
                UserStatusLastWeek, UserStatusLastMonth, UserStatusEmpty,
            )
            client = telegram_dm_service._clients.get(account.id)
            if client and client.is_connected():
                entity = await client.get_entity(dialog.peer_id)
                if hasattr(entity, "status") and entity.status:
                    s = entity.status
                    if isinstance(s, UserStatusOnline):
                        peer_status = {"status": "online", "last_seen": None, "possibly_blocked": False}
                    elif isinstance(s, UserStatusOffline):
                        peer_status = {
                            "status": "offline",
                            "last_seen": s.was_online.isoformat() if s.was_online else None,
                            "possibly_blocked": False,
                        }
                    elif isinstance(s, UserStatusRecently):
                        peer_status = {"status": "recently", "last_seen": None, "possibly_blocked": False}
                    elif isinstance(s, UserStatusLastWeek):
                        peer_status = {"status": "within_week", "last_seen": None, "possibly_blocked": False}
                    elif isinstance(s, UserStatusLastMonth):
                        peer_status = {"status": "within_month", "last_seen": None, "possibly_blocked": False}
                    elif isinstance(s, UserStatusEmpty):
                        peer_status = {"status": "long_ago", "last_seen": None, "possibly_blocked": True}
                    else:
                        peer_status = {"status": "unknown", "last_seen": None, "possibly_blocked": False}
                elif hasattr(entity, "status") and entity.status is None:
                    # Hidden status — could be privacy or block
                    peer_status = {"status": "hidden", "last_seen": None, "possibly_blocked": True}
        except Exception as e:
            logger.debug(f"Failed to get peer status for dialog {dialog_id}: {e}")

        if not already_connected:
            await telegram_dm_service.disconnect_account(account.id)

        return {
            "messages": formatted,
            "peer_name": dialog.peer_name,
            "peer_username": dialog.peer_username,
            "account_phone": account.phone,
            "campaign_id": dialog.campaign_id,
            "tag": dialog.inbox_tag,
            "peer_status": peer_status,
        }
    except HTTPException:
        raise
    except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError):
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except Exception:
            pass
        raise HTTPException(401, "Session expired — re-authorize the account")
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except:
            pass
        raise HTTPException(500, f"Failed to fetch messages: {str(e)[:100]}")


@router.get("/inbox/dialogs/{dialog_id}/typing")
async def get_dialog_typing(
    dialog_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Check if the peer in this dialog is currently typing."""
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        return {"typing": False}
    dm_result = await session.execute(
        select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone)
    )
    account = None
    for c in dm_result.scalars().all():
        if telegram_dm_service.is_connected(c.id) and c.string_session:
            account = c
            break
    if not account:
        return {"typing": False}

    is_typing = telegram_dm_service.get_typing_status(account.id, dialog.peer_id)
    return {"typing": is_typing}


@router.post("/inbox/dialogs/{dialog_id}/send")
async def send_dialog_message(
    dialog_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Send a message in a dialog via telegram_dm_service."""
    from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Message text required")

    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    # Resolve to DM account via phone
    tg_acc_send = await session.get(TgAccount, dialog.account_id)
    if not tg_acc_send:
        raise HTTPException(400, "Outreach account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc_send.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account or account.auth_status != "active":
        raise HTTPException(400, "Account not active")
    if not account.string_session:
        raise HTTPException(400, "Account has no string_session")

    proxy_cfg = await _resolve_dm_proxy(account, session)

    # Check if already connected — avoid disconnect at the end if so
    already_connected = telegram_dm_service.is_connected(account.id)

    try:
        if not already_connected:
            ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
            if not ok:
                raise HTTPException(500, "Failed to connect account")

        result = await telegram_dm_service.send_message(account.id, dialog.peer_id, text, reply_to=body.get("replyTo"), parse_mode=body.get("parseMode"))

        if not already_connected:
            await telegram_dm_service.disconnect_account(account.id)

        if result.get("success"):
            # Update dialog cache
            dialog.last_message_text = text[:500]
            dialog.last_message_at = datetime.utcnow()
            dialog.last_message_outbound = True
            await session.commit()

        return result
    except HTTPException:
        raise
    except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError):
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except Exception:
            pass
        raise HTTPException(401, "Session expired — re-authorize the account")
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except:
            pass
        raise HTTPException(500, f"Send failed: {str(e)[:100]}")


@router.post("/inbox/dialogs/{dialog_id}/send-file")
async def send_dialog_file(
    dialog_id: int,
    file: UploadFile = File(...),
    caption: str = Form(""),
    parse_mode: str = Form(""),
    reply_to: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session),
):
    """Send a file/media in a dialog via telegram_dm_service."""
    from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError
    import os, tempfile, shutil

    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    # Resolve to DM account via phone (same logic as send_dialog_message)
    tg_acc_send = await session.get(TgAccount, dialog.account_id)
    if not tg_acc_send:
        raise HTTPException(400, "Outreach account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc_send.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account or account.auth_status != "active":
        raise HTTPException(400, "Account not active")
    if not account.string_session:
        raise HTTPException(400, "Account has no string_session")

    proxy_cfg = await _resolve_dm_proxy(account, session)
    already_connected = telegram_dm_service.is_connected(account.id)

    # Save uploaded file to temp location
    suffix = os.path.splitext(file.filename or "file")[1] or ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="tg_inbox_")
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp.close()

        if not already_connected:
            ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
            if not ok:
                raise HTTPException(500, "Failed to connect account")

        result = await telegram_dm_service.send_file(
            account.id, dialog.peer_id, tmp.name,
            caption=caption.strip() or None,
            parse_mode=parse_mode or None,
            reply_to=reply_to,
        )

        if not already_connected:
            await telegram_dm_service.disconnect_account(account.id)

        if result.get("success"):
            dialog.last_message_text = (caption.strip() or f"[{file.filename or 'File'}]")[:500]
            dialog.last_message_at = _dt.utcnow()
            dialog.last_message_outbound = True
            await session.commit()

        return result
    except HTTPException:
        raise
    except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError):
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except Exception:
            pass
        raise HTTPException(401, "Session expired — re-authorize the account")
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except:
            pass
        raise HTTPException(500, f"Send file failed: {str(e)[:100]}")
    finally:
        try:
            os.unlink(tmp.name)
        except:
            pass


@router.get("/inbox/dialogs/{dialog_id}/media/{msg_id}")
async def get_dialog_media(
    dialog_id: int,
    msg_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Download media from a specific message in a dialog."""
    from fastapi.responses import Response

    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        raise HTTPException(400, "Account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account or not account.string_session:
        raise HTTPException(400, "Account not available")

    proxy_cfg = await _resolve_dm_proxy(account, session)
    already_connected = telegram_dm_service.is_connected(account.id)

    try:
        if not already_connected:
            ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
            if not ok:
                raise HTTPException(500, "Failed to connect account")

        result = await telegram_dm_service.download_message_media(account.id, dialog.peer_id, msg_id)

        if not already_connected:
            await telegram_dm_service.disconnect_account(account.id)

        if not result:
            raise HTTPException(404, "No media found for this message")

        data, content_type = result
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(account.id)
        except:
            pass
        raise HTTPException(500, f"Failed to download media: {str(e)[:100]}")


@router.patch("/inbox/dialogs/{dialog_id}/tag")
async def tag_dialog(
    dialog_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Tag an inbox dialog. Tags are per-dialog (per account+peer), not global."""
    tag = body.get("tag", "")

    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    dialog.inbox_tag = tag or None
    await session.commit()
    return {"ok": True}



@router.delete("/inbox/dialogs/{dialog_id}/messages/{msg_id}")
async def delete_dialog_message(
    dialog_id: int, msg_id: int,
    revoke: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Delete a message in a dialog."""
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")
    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        raise HTTPException(400, "Account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account:
        raise HTTPException(400, "No DM account available")
    proxy_cfg = await _resolve_dm_proxy(account, session)
    already = telegram_dm_service.is_connected(account.id)
    if not already:
        ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
        if not ok:
            raise HTTPException(500, "Failed to connect")
    try:
        result = await telegram_dm_service.delete_messages(account.id, dialog.peer_id, [msg_id], revoke=revoke)
        if not already:
            await telegram_dm_service.disconnect_account(account.id)
        return result
    except Exception as e:
        if not already:
            try: await telegram_dm_service.disconnect_account(account.id)
            except: pass
        raise HTTPException(500, f"Delete failed: {str(e)[:100]}")


@router.post("/inbox/dialogs/{dialog_id}/messages/{msg_id}/react")
async def react_dialog_message(
    dialog_id: int, msg_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Send a reaction to a message."""
    emoji = body.get("emoji", "")
    if not emoji:
        raise HTTPException(400, "Emoji required")
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")
    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        raise HTTPException(400, "Account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account:
        raise HTTPException(400, "No DM account available")
    proxy_cfg = await _resolve_dm_proxy(account, session)
    already = telegram_dm_service.is_connected(account.id)
    if not already:
        ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
        if not ok:
            raise HTTPException(500, "Failed to connect")
    try:
        result = await telegram_dm_service.send_reaction(account.id, dialog.peer_id, msg_id, emoji)
        if not already:
            await telegram_dm_service.disconnect_account(account.id)
        return result
    except Exception as e:
        if not already:
            try: await telegram_dm_service.disconnect_account(account.id)
            except: pass
        raise HTTPException(500, f"React failed: {str(e)[:100]}")



@router.put("/inbox/dialogs/{dialog_id}/messages/{msg_id}/edit")
async def edit_dialog_message(
    dialog_id: int, msg_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Edit a sent message in a dialog."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Message text required")
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")
    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        raise HTTPException(400, "Account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account:
        raise HTTPException(400, "No DM account available")
    proxy_cfg = await _resolve_dm_proxy(account, session)
    already = telegram_dm_service.is_connected(account.id)
    if not already:
        ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
        if not ok:
            raise HTTPException(500, "Failed to connect")
    try:
        result = await telegram_dm_service.edit_message(
            account.id, dialog.peer_id, msg_id,
            text, parse_mode=body.get("parseMode"),
        )
        if not already:
            await telegram_dm_service.disconnect_account(account.id)
        return result
    except Exception as e:
        if not already:
            try: await telegram_dm_service.disconnect_account(account.id)
            except: pass
        raise HTTPException(500, f"Edit failed: {str(e)[:100]}")


@router.post("/inbox/dialogs/{dialog_id}/forward")
async def forward_dialog_messages(
    dialog_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Forward messages to another dialog using Telethon forward_messages."""
    target_dialog_id = body.get("target_dialog_id")
    msg_ids = body.get("msg_ids", [])
    if not target_dialog_id or not msg_ids:
        raise HTTPException(400, "target_dialog_id and msg_ids required")

    dialog = await session.get(TgInboxDialog, dialog_id)
    target = await session.get(TgInboxDialog, target_dialog_id)
    if not dialog or not target:
        raise HTTPException(404, "Dialog not found")

    tg_acc = await session.get(TgAccount, dialog.account_id)
    if not tg_acc:
        raise HTTPException(400, "Account not found")
    dm_r = await session.execute(select(TelegramDMAccount).where(TelegramDMAccount.phone == tg_acc.phone))
    dm_candidates = dm_r.scalars().all()
    account = next((c for c in dm_candidates if telegram_dm_service.is_connected(c.id) and c.string_session), None)
    if not account:
        account = next((c for c in dm_candidates if c.string_session), None)
    if not account:
        raise HTTPException(400, "No DM account available")

    proxy_cfg = await _resolve_dm_proxy(account, session)
    already = telegram_dm_service.is_connected(account.id)
    if not already:
        ok = await telegram_dm_service.connect_account(account.id, account.string_session, proxy_cfg)
        if not ok:
            raise HTTPException(500, "Failed to connect")
    try:
        result = await telegram_dm_service.forward_messages(account.id, dialog.peer_id, msg_ids, target.peer_id)
        if not already:
            await telegram_dm_service.disconnect_account(account.id)
        return result
    except Exception as e:
        if not already:
            try: await telegram_dm_service.disconnect_account(account.id)
            except: pass
        raise HTTPException(500, f"Forward failed: {str(e)[:100]}")



@router.post("/inbox/dialogs/{dialog_id}/read")
async def mark_dialog_read(dialog_id: int, session: AsyncSession = Depends(get_session)):
    """Mark a dialog as read (clear unread_count)."""
    dialog = await session.get(TgInboxDialog, dialog_id)
    if dialog:
        dialog.unread_count = 0
        await session.commit()
    return {"ok": True}


@router.post("/inbox/dialogs/{dialog_id}/unread")
async def mark_dialog_unread(dialog_id: int, session: AsyncSession = Depends(get_session)):
    """Mark a dialog as unread (set unread_count = 1)."""
    dialog = await session.get(TgInboxDialog, dialog_id)
    if dialog:
        dialog.unread_count = 1
        await session.commit()
    return {"ok": True}


@router.get("/inbox/dialogs/{dialog_id}/crm")
async def get_dialog_crm(dialog_id: int, session: AsyncSession = Depends(get_session)):
    """Get CRM contact data for a dialog (by peer username)."""
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")
    if not dialog.peer_username:
        return {"contact": None}
    result = await session.execute(
        select(TgContact).where(TgContact.username == dialog.peer_username)
    )
    contact = result.scalar()
    if not contact:
        return {"contact": None}
    return {"contact": {
        "id": contact.id,
        "username": contact.username,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "company_name": contact.company_name,
        "phone": contact.phone,
        "status": contact.status.value if hasattr(contact.status, "value") else contact.status,
        "tags": contact.tags or [],
        "notes": _parse_notes(contact.notes),
        "custom_data": contact.custom_data or {},
        "campaigns": contact.campaigns or [],
        "total_messages_sent": contact.total_messages_sent or 0,
        "total_replies_received": contact.total_replies_received or 0,
        "first_contacted_at": contact.first_contacted_at.isoformat() if contact.first_contacted_at else None,
        "last_contacted_at": contact.last_contacted_at.isoformat() if contact.last_contacted_at else None,
        "last_reply_at": contact.last_reply_at.isoformat() if contact.last_reply_at else None,
    }}


@router.get("/inbox/campaign-tags")
async def list_inbox_campaign_tags(session: AsyncSession = Depends(get_session)):
    """Get all unique tags across campaigns for Inbox tag filtering."""
    result = await session.execute(select(TgCampaign.tags).where(TgCampaign.tags.isnot(None)))
    all_tags = set()
    for (tags,) in result.all():
        if isinstance(tags, list):
            for t in tags:
                if t:
                    all_tags.add(t)
    return sorted(all_tags)


@router.post("/inbox/sync")
async def trigger_inbox_sync(
    account_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger inbox sync for one telegram_dm_account or all active DM accounts."""
    if account_id:
        count = await inbox_sync_service.sync_account(account_id, session)
        return {"ok": True, "synced": count}
    else:
        count = await inbox_sync_service.sync_all()
        return {"ok": True, "synced": count}


@router.post("/inbox/new-chat")
async def create_new_chat(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Resolve @username via Telegram and create an inbox dialog.

    Requires account_id (telegram_dm_accounts.id) and username.
    Returns existing dialog if one already exists for this account+peer.
    """
    dm_account_id = body.get("account_id")
    username = (body.get("username") or "").strip().lstrip("@")
    if not dm_account_id or not username:
        raise HTTPException(400, "account_id and username required")

    # Validate DM account
    dm_acc = await session.get(TelegramDMAccount, dm_account_id)
    if not dm_acc or not dm_acc.string_session or dm_acc.auth_status != "active":
        raise HTTPException(400, "Account not active or missing session")

    # Resolve DM account → TG outreach account via phone
    tg_account_id = None
    if dm_acc.phone:
        row = (await session.execute(
            select(TgAccount.id).where(TgAccount.phone == dm_acc.phone).limit(1)
        )).first()
        if row:
            tg_account_id = row[0]
    if not tg_account_id:
        if not dm_acc.phone:
            raise HTTPException(400, "Account has no phone number")
        # Auto-create TgAccount so TgInboxDialog FK is satisfied
        new_tg = TgAccount(
            phone=dm_acc.phone,
            username=dm_acc.username,
            first_name=dm_acc.first_name,
            last_name=getattr(dm_acc, "last_name", None),
            string_session=dm_acc.string_session,
        )
        session.add(new_tg)
        await session.flush()
        tg_account_id = new_tg.id

    # Connect and resolve username
    proxy_cfg = await _resolve_dm_proxy(dm_acc, session)
    already_connected = telegram_dm_service.is_connected(dm_account_id)
    try:
        if not already_connected:
            ok = await telegram_dm_service.connect_account(dm_account_id, dm_acc.string_session, proxy_cfg)
            if not ok:
                raise HTTPException(500, "Failed to connect account")

        result = await telegram_dm_service.resolve_username(dm_account_id, username)
        if not result.get("success"):
            if not already_connected:
                await telegram_dm_service.disconnect_account(dm_account_id)
            raise HTTPException(404, result.get("error", "Username not found"))

        peer_id = result["peer_id"]
        peer_name = result["peer_name"]
        peer_username = result.get("peer_username")

        # Check if dialog already exists
        all_account_ids = [tg_account_id, dm_account_id]
        existing = (await session.execute(
            select(TgInboxDialog).where(
                TgInboxDialog.account_id.in_(all_account_ids),
                TgInboxDialog.peer_id == peer_id,
            ).limit(1)
        )).scalars().first()

        if existing:
            if not already_connected:
                await telegram_dm_service.disconnect_account(dm_account_id)
            return {
                "id": existing.id,
                "account_id": existing.account_id,
                "peer_id": existing.peer_id,
                "peer_name": existing.peer_name,
                "peer_username": existing.peer_username,
                "last_message_text": existing.last_message_text,
                "last_message_at": existing.last_message_at.isoformat() if existing.last_message_at else None,
                "last_message_outbound": existing.last_message_outbound,
                "unread_count": existing.unread_count,
                "campaign_id": existing.campaign_id,
                "tag": existing.inbox_tag,
                "is_new": False,
            }

        # Create new dialog
        dialog = TgInboxDialog(
            account_id=tg_account_id,
            peer_id=peer_id,
            peer_name=peer_name,
            peer_username=peer_username,
            last_message_text=None,
            last_message_at=datetime.utcnow(),
            last_message_outbound=None,
            unread_count=0,
        )
        session.add(dialog)
        await session.commit()
        await session.refresh(dialog)

        if not already_connected:
            await telegram_dm_service.disconnect_account(dm_account_id)

        return {
            "id": dialog.id,
            "account_id": dialog.account_id,
            "peer_id": dialog.peer_id,
            "peer_name": dialog.peer_name,
            "peer_username": dialog.peer_username,
            "last_message_text": None,
            "last_message_at": dialog.last_message_at.isoformat() if dialog.last_message_at else None,
            "last_message_outbound": None,
            "unread_count": 0,
            "campaign_id": None,
            "tag": None,
            "is_new": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(dm_account_id)
        except:
            pass
        raise HTTPException(500, f"New chat failed: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════════════════
# BLACKLIST
# ═══════════════════════════════════════════════════════════════════════

import re

_TG_LINK_RE = re.compile(
    r'(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', re.IGNORECASE
)


def _normalize_username(raw: str) -> str | None:
    """Normalize various TG username formats to bare username (no @)."""
    raw = raw.strip()
    if not raw:
        return None
    # t.me/user or telegram.me/user link
    m = _TG_LINK_RE.match(raw)
    if m:
        return m.group(1).lower()
    # @username or plain username
    return raw.lstrip("@").lower()


@router.get("/blacklist", response_model=TgBlacklistListResponse)
async def list_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q = select(TgBlacklist)
    count_q = select(func.count(TgBlacklist.id))
    if search:
        q = q.where(TgBlacklist.username.ilike(f"%{search}%"))
        count_q = count_q.where(TgBlacklist.username.ilike(f"%{search}%"))
    total = (await session.execute(count_q)).scalar() or 0
    rows = (await session.execute(
        q.order_by(desc(TgBlacklist.created_at))
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return TgBlacklistListResponse(
        items=[TgBlacklistResponse.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/blacklist/upload")
async def upload_blacklist(data: TgBlacklistUploadText, session: AsyncSession = Depends(get_session)):
    """Upload usernames to blacklist. Supports @user, t.me/user, https://t.me/user, telegram.me/user."""
    added = 0
    skipped = 0
    for line in data.raw_text.strip().splitlines():
        username = _normalize_username(line)
        if not username:
            continue
        existing = await session.execute(
            select(TgBlacklist).where(TgBlacklist.username == username)
        )
        if existing.scalar():
            skipped += 1
            continue
        session.add(TgBlacklist(username=username, reason=data.reason))
        added += 1
    await session.commit()
    return {"ok": True, "added": added, "skipped": skipped}


@router.delete("/blacklist/{entry_id}")
async def delete_blacklist_entry(entry_id: int, session: AsyncSession = Depends(get_session)):
    entry = await session.get(TgBlacklist, entry_id)
    if not entry:
        raise HTTPException(404, "Blacklist entry not found")
    await session.delete(entry)
    await session.commit()
    return {"ok": True}


@router.post("/blacklist/bulk-delete")
async def bulk_delete_blacklist(data: dict, session: AsyncSession = Depends(get_session)):
    ids = data.get("ids", [])
    if ids:
        await session.execute(sa_delete(TgBlacklist).where(TgBlacklist.id.in_(ids)))
        await session.commit()
    return {"ok": True, "deleted": len(ids)}


@router.get("/blacklist/count")
async def blacklist_count(session: AsyncSession = Depends(get_session)):
    total = (await session.execute(select(func.count(TgBlacklist.id)))).scalar() or 0
    return {"total": total}


# ── Notification Bot Endpoints ────────────────────────────────────────
from app.models.telegram_outreach import TgOutreachNotifSub
from app.schemas.telegram_outreach import TgNotifSubResponse, TgNotifSubUpdate, TgNotifBotInfoResponse


@router.get("/notifications/bot-info", response_model=TgNotifBotInfoResponse)
async def get_notif_bot_info(session: AsyncSession = Depends(get_session)):
    """Get bot info and deep link for connecting."""
    from app.core.config import settings as _s
    import httpx

    bot_username = None
    token = _s.TELEGRAM_BOT_TOKEN
    if token:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"https://api.telegram.org/bot{token}/getMe")
                data = resp.json()
                if data.get("ok"):
                    bot_username = data["result"].get("username")
        except Exception:
            pass

    total = (await session.execute(
        select(func.count(TgOutreachNotifSub.id)).where(TgOutreachNotifSub.is_active == True)
    )).scalar() or 0

    deep_link = f"https://t.me/{bot_username}?start=tg_outreach" if bot_username else None
    return TgNotifBotInfoResponse(
        bot_username=bot_username,
        deep_link=deep_link,
        subscribers_count=total,
    )


@router.get("/notifications/subscribers", response_model=list[TgNotifSubResponse])
async def list_notif_subscribers(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TgOutreachNotifSub).order_by(TgOutreachNotifSub.created_at.desc())
    )
    return result.scalars().all()


@router.put("/notifications/subscribers/{sub_id}", response_model=TgNotifSubResponse)
async def update_notif_subscriber(
    sub_id: int,
    data: TgNotifSubUpdate,
    session: AsyncSession = Depends(get_session),
):
    sub = await session.get(TgOutreachNotifSub, sub_id)
    if not sub:
        raise HTTPException(404, "Subscriber not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    sub.updated_at = _dt.utcnow()
    await session.commit()
    await session.refresh(sub)
    return sub


@router.delete("/notifications/subscribers/{sub_id}")
async def delete_notif_subscriber(sub_id: int, session: AsyncSession = Depends(get_session)):
    sub = await session.get(TgOutreachNotifSub, sub_id)
    if not sub:
        raise HTTPException(404, "Subscriber not found")
    await session.delete(sub)
    await session.commit()
    return {"ok": True}


@router.post("/notifications/test")
async def send_test_notification(session: AsyncSession = Depends(get_session)):
    """Send a test notification to all active subscribers."""
    from app.services.tg_outreach_notif_service import tg_outreach_notif_service

    result = await session.execute(
        select(TgOutreachNotifSub).where(TgOutreachNotifSub.is_active == True)
    )
    subs = result.scalars().all()
    sent = 0
    for sub in subs:
        msg_id = await tg_outreach_notif_service._send_message(
            sub.chat_id,
            "🔔 <b>Test Notification</b>\n\nTG Outreach notifications are working!",
        )
        if msg_id:
            sent += 1
    return {"ok": True, "sent": sent, "total": len(subs)}
