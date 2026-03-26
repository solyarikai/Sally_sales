"""
Telegram Outreach API router.

Manages Telegram accounts, proxy groups, outreach campaigns,
message sequences, and recipients.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db import get_session
from app.models.telegram_outreach import (
    TgAccount, TgAccountTag, TgAccountTagLink,
    TgProxyGroup, TgProxy,
    TgCampaign, TgCampaignAccount,
    TgRecipient, TgSequence, TgSequenceStep, TgStepVariant, TgOutreachMessage,
    TgAccountStatus, TgSpamblockType, TgCampaignStatus, TgRecipientStatus,
)
from app.schemas.telegram_outreach import (
    TgProxyGroupCreate, TgProxyGroupUpdate, TgProxyGroupResponse,
    TgProxyCreate, TgProxyBulkCreate, TgProxyResponse,
    TgAccountTagCreate, TgAccountTagResponse,
    TgAccountCreate, TgAccountUpdate, TgAccountResponse, TgAccountListResponse,
    TgCampaignCreate, TgCampaignUpdate, TgCampaignResponse, TgCampaignListResponse,
    TgCampaignStatsResponse,
    TgRecipientResponse, TgRecipientListResponse,
    TgRecipientUploadText, TgRecipientUploadCSVMapping,
    TgSequenceSchema, TgSequenceStepSchema, TgStepVariantSchema,
    TgSequencePreviewRequest, TgSequencePreviewResponse,
    TgOutreachMessageResponse, TgOutreachMessageListResponse,
    TgBulkAssignProxy, TgBulkTag, TgBulkAccountIds,
    TgTeleRaptorImportRequest, TgTeleRaptorImportResponse,
)

router = APIRouter(prefix="/telegram-outreach", tags=["Telegram Outreach"])


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


def _parse_session_date(register_time: Optional[str], tgid: Optional[int] = None):
    """Get account registration date from register_time string or estimate from tgid."""
    from datetime import datetime as dt
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

    for proxy in proxies:
        check = await _check_single_proxy(proxy)
        proxy.is_active = check["alive"]
        proxy.last_checked_at = func.now()

        if check["alive"]:
            alive_count += 1
        else:
            dead_count += 1
            if auto_delete:
                deleted_ids.append(proxy.id)
                await session.delete(proxy)

        results.append({
            "proxy_id": proxy.id,
            "host": proxy.host,
            "port": proxy.port,
            **check,
        })

    return {
        "total": len(proxies),
        "alive": alive_count,
        "dead": dead_count,
        "deleted": len(deleted_ids),
        "deleted_ids": deleted_ids,
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
    session: AsyncSession = Depends(get_session),
):
    query = select(TgAccount).options(selectinload(TgAccount.tags), selectinload(TgAccount.proxy_group))
    count_query = select(func.count(TgAccount.id))

    # Filters
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

    # Backfill missing country_code and session_created_at
    dirty = False
    for acc in accounts:
        if not acc.country_code and acc.phone:
            acc.country_code = _detect_country(acc.phone)
            if acc.country_code:
                dirty = True
        if not acc.session_created_at:
            est = _parse_session_date(None, acc.telegram_user_id)
            acc.session_created_at = est or acc.last_connected_at or acc.created_at
            if acc.session_created_at:
                dirty = True
    if dirty:
        await session.commit()

    items = []
    for acc in accounts:
        # Count campaigns
        camp_count_q = await session.execute(
            select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.account_id == acc.id)
        )
        items.append(TgAccountResponse(
            id=acc.id, phone=acc.phone, username=acc.username,
            first_name=acc.first_name, last_name=acc.last_name, bio=acc.bio,
            device_model=acc.device_model, system_version=acc.system_version,
            app_version=acc.app_version, lang_code=acc.lang_code,
            system_lang_code=acc.system_lang_code,
            status=acc.status.value if acc.status else "active",
            spamblock_type=acc.spamblock_type.value if acc.spamblock_type else "none",
            daily_message_limit=acc.daily_message_limit,
            messages_sent_today=acc.messages_sent_today,
            total_messages_sent=acc.total_messages_sent,
            proxy_group_id=acc.proxy_group_id,
            proxy_group_name=acc.proxy_group.name if acc.proxy_group else None,
            assigned_proxy_id=acc.assigned_proxy_id,
            tags=[TgAccountTagResponse.model_validate(t) for t in acc.tags],
            campaigns_count=camp_count_q.scalar() or 0,
            country_code=acc.country_code,
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

    account = TgAccount(
        phone=data.phone, username=data.username,
        first_name=data.first_name, last_name=data.last_name, bio=data.bio,
        api_id=data.api_id, api_hash=data.api_hash,
        device_model=data.device_model, system_version=data.system_version,
        app_version=data.app_version, lang_code=data.lang_code,
        system_lang_code=data.system_lang_code, two_fa_password=data.two_fa_password,
        session_file=data.session_file_name,
        country_code=_detect_country(data.phone),
        session_created_at=func.now(),
    )
    session.add(account)
    await session.flush()

    return TgAccountResponse(
        id=account.id, phone=account.phone, username=account.username,
        first_name=account.first_name, last_name=account.last_name, bio=account.bio,
        device_model=account.device_model, system_version=account.system_version,
        app_version=account.app_version, lang_code=account.lang_code,
        system_lang_code=account.system_lang_code,
        status="active", spamblock_type="none",
        daily_message_limit=account.daily_message_limit,
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
        .options(selectinload(TgAccount.tags), selectinload(TgAccount.proxy_group))
    )
    account = result.scalar_one()
    camp_count_q = await session.execute(
        select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.account_id == account.id)
    )
    return TgAccountResponse(
        id=account.id, phone=account.phone, username=account.username,
        first_name=account.first_name, last_name=account.last_name, bio=account.bio,
        device_model=account.device_model, system_version=account.system_version,
        app_version=account.app_version, lang_code=account.lang_code,
        system_lang_code=account.system_lang_code,
        status=account.status.value, spamblock_type=account.spamblock_type.value,
        daily_message_limit=account.daily_message_limit,
        messages_sent_today=account.messages_sent_today,
        total_messages_sent=account.total_messages_sent,
        proxy_group_id=account.proxy_group_id,
        proxy_group_name=account.proxy_group.name if account.proxy_group else None,
        assigned_proxy_id=account.assigned_proxy_id,
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
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.proxy_group_id = data.proxy_group_id
    return {"ok": True, "count": len(data.account_ids)}


@router.post("/accounts/bulk-set-limit")
async def bulk_set_limit(data: TgBulkAccountIds, daily_message_limit: int = Query(..., ge=1),
                          session: AsyncSession = Depends(get_session)):
    """Set daily message limit for multiple accounts."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.daily_message_limit = daily_message_limit
    return {"ok": True, "count": len(data.account_ids), "daily_message_limit": daily_message_limit}


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
    "ThinkPadL13", "15t-ed002", "DW0010", "S533EA", "R7-3700U",
    "Latitude5401", "A315-54K", "RZ09-0281CE53", "FHD-G15", "X512JA",
    "OmenX-17", "7DF52EA", "81XH", "A11SCS", "Precision3561",
    "13-aw2000", "81UR", "XPS13-9380", "RZ09-0367", "15Z980",
    "ThinkPadT590", "Aspire314", "DW1084", "NP930X2K", "C214MA",
]
SYSTEM_VERSIONS = ["Windows 10", "Windows 11"]
APP_VERSIONS = ["6.5.1 x64", "6.6.2 x64"]
LANG_PRESETS = ["en", "pt", "es", "de", "fr", "it", "nl", "ru"]
SYSTEM_LANG_PRESETS = ["en-US", "pt-PT", "es-ES", "de-DE", "fr-FR", "it-IT", "nl-NL", "ru-RU"]


@router.post("/accounts/bulk-randomize-device")
async def bulk_randomize_device(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Randomize device_model + system_version from TeleRaptor presets for selected accounts."""
    import random

    updated = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        account.device_model = random.choice(DEVICE_PRESETS)
        account.system_version = random.choice(SYSTEM_VERSIONS)
        account.app_version = random.choice(APP_VERSIONS)
        updated.append({"id": aid, "device_model": account.device_model,
                        "system_version": account.system_version, "app_version": account.app_version})
    return {"ok": True, "count": len(updated), "updated": updated}


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
    synced = await _auto_sync_accounts([u["id"] for u in updated], session)
    return {"ok": True, "count": len(updated), "synced": synced, "updated": updated}


@router.post("/accounts/bulk-set-photo")
async def bulk_set_photo(
    account_ids_json: str = Form(...),
    photos: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Set profile photos for selected accounts.
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

        # Save to disk
        ext = os.path.splitext(fname)[1] or ".jpg"
        photo_path = f"{photos_dir}/{account.phone}{ext}"
        with open(photo_path, "wb") as f:
            f.write(content)
        account.profile_photo_path = photo_path
        updated += 1

    return {"ok": True, "count": updated, "photos_uploaded": len(photo_contents)}


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
    """Sync profile (name, bio, username) to Telegram for selected accounts."""
    synced = 0
    errors = []
    for aid in data.account_ids:
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
            errors.append(f"{account.phone}: {str(e)[:50]}")
    return {"ok": True, "synced": synced, "errors": errors}


@router.post("/accounts/bulk-set-bio")
async def bulk_set_bio(data: TgBulkAccountIds, bio: str = Query(...),
                        session: AsyncSession = Depends(get_session)):
    """Set bio for multiple accounts + auto-sync to Telegram."""
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if account:
            account.bio = bio
    await session.flush()
    synced = await _auto_sync_accounts(data.account_ids, session)
    return {"ok": True, "count": len(data.account_ids), "synced": synced}


@router.post("/accounts/bulk-set-2fa")
async def bulk_set_2fa(data: TgBulkAccountIds, password: str = Query(...),
                        session: AsyncSession = Depends(get_session)):
    """Set 2FA password for multiple accounts — both in DB and on Telegram."""
    updated = 0
    tg_synced = 0
    errors = []
    for aid in data.account_ids:
        account = await session.get(TgAccount, aid)
        if not account:
            continue
        old_password = account.two_fa_password
        account.two_fa_password = password
        updated += 1

        # Try to change 2FA on Telegram if session exists
        if account.api_id and account.api_hash and telegram_engine.session_file_exists(account.phone):
            try:
                kwargs = _account_connect_kwargs(account)
                await telegram_engine.connect(aid, **kwargs)
                client = telegram_engine.get_client(aid)
                if client and await client.is_user_authorized():
                    await client.edit_2fa(current_password=old_password or '', new_password=password)
                    tg_synced += 1
                await telegram_engine.disconnect(aid)
            except Exception as e:
                errors.append(f"{account.phone}: {str(e)[:50]}")
    return {"ok": True, "updated": updated, "tg_synced": tg_synced, "errors": errors}


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
    """Update privacy settings for multiple accounts via Telethon."""
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

    params = {
        "last_online": last_online, "phone_visibility": phone_visibility,
        "profile_pic_visibility": profile_pic_visibility, "bio_visibility": bio_visibility,
        "forwards_visibility": forwards_visibility, "calls": calls,
        "private_messages": private_messages,
    }
    active_params = {k: v for k, v in params.items() if v and v in PRIVACY_MAP}

    if not active_params:
        return {"ok": True, "message": "No privacy settings specified"}

    updated = 0
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
            for key_name, value in active_params.items():
                if key_name in KEY_MAP:
                    await client(functions.account.SetPrivacyRequest(
                        key=KEY_MAP[key_name](), rules=PRIVACY_MAP[value]
                    ))
            await telegram_engine.disconnect(aid)
            updated += 1
        except Exception as e:
            errors.append(f"{account.phone}: {str(e)[:50]}")
    return {"ok": True, "updated": updated, "errors": errors}


@router.post("/accounts/bulk-revoke-sessions")
async def bulk_revoke_sessions(data: TgBulkAccountIds, session: AsyncSession = Depends(get_session)):
    """Revoke all other sessions for selected accounts."""
    from telethon import functions

    revoked = 0
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
            result = await client(functions.auth.GetAuthorizationsRequest())
            for auth in result.authorizations:
                if not auth.current:
                    try:
                        await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                    except Exception:
                        pass
            await telegram_engine.disconnect(aid)
            revoked += 1
        except Exception as e:
            errors.append(f"{account.phone}: {str(e)[:50]}")
    return {"ok": True, "revoked": revoked, "errors": errors}


@router.post("/accounts/bulk-reauthorize")
async def bulk_reauthorize(
    data: TgBulkAccountIds,
    new_2fa: Optional[str] = Query(None),
    close_old_sessions: bool = Query(True),
    session: AsyncSession = Depends(get_session),
):
    """Re-authorize accounts with randomized device params + optionally new 2FA."""
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

            kwargs = _account_connect_kwargs(account)
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
                            except Exception:
                                pass
                except Exception:
                    pass

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

        account = TgAccount(
            phone=phone,
            username=raw.username,
            first_name=raw.first_name,
            last_name=raw.last_name,
            api_id=raw.app_id,
            api_hash=raw.app_hash,
            device_model=raw.sdk or "PC 64bit",
            system_version=raw.device or "Windows 10",
            app_version=raw.app_version or "6.5.1 x64",
            lang_code=raw.lang_pack or "en",
            system_lang_code=raw.system_lang_pack or "en-US",
            two_fa_password=raw.twoFA,
            session_file=raw.session_file,
            status=status,
            spamblock_type=spamblock_type,
            total_messages_sent=raw.stats_spam_count or 0,
            last_connected_at=last_connected,
            country_code=_detect_country(phone),
            telegram_user_id=raw.tgid,
            session_created_at=_parse_session_date(raw.register_time, raw.tgid) or last_connected or func.now(),
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

        account = TgAccount(
            phone=phone,
            username=json_data.get("username"),
            first_name=json_data.get("first_name"),
            last_name=json_data.get("last_name"),
            api_id=json_data.get("app_id"),
            api_hash=json_data.get("app_hash"),
            device_model=json_data.get("sdk") or "PC 64bit",
            system_version=json_data.get("device") or "Windows 10",
            app_version=json_data.get("app_version") or "6.5.1 x64",
            lang_code=json_data.get("lang_pack") or "en",
            system_lang_code=json_data.get("system_lang_pack") or "en-US",
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

        # Save session file
        if pair["has_session"]:
            save_session_file(phone, pair["session_bytes"])
            sessions_saved += 1

        added += 1

    if added > 0:
        await session.flush()

    return {
        "added": added,
        "skipped": skipped,
        "sessions_saved": sessions_saved,
        "total_files": len(all_files),
        "pairs_found": len(pairs),
        "errors": errors,
        "has_tdata": tdata_files is not None,
    }


@router.post("/accounts/{account_id}/convert-to-tdata")
async def convert_account_to_tdata(account_id: int, session: AsyncSession = Depends(get_session)):
    """Convert account's .session to tdata format. Returns download info."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

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


@router.post("/accounts/{account_id}/convert-from-tdata")
async def convert_account_from_tdata(account_id: int, session: AsyncSession = Depends(get_session)):
    """Convert account's tdata to .session format."""
    account = await session.get(TgAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

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
async def list_campaigns(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(TgCampaign).order_by(desc(TgCampaign.created_at)))
    campaigns = result.scalars().all()
    items = []
    for c in campaigns:
        acc_count_q = await session.execute(
            select(func.count(TgCampaignAccount.id)).where(TgCampaignAccount.campaign_id == c.id)
        )
        items.append(TgCampaignResponse(
            id=c.id, name=c.name, status=c.status.value,
            daily_message_limit=c.daily_message_limit,
            timezone=c.timezone, send_from_hour=c.send_from_hour, send_to_hour=c.send_to_hour,
            delay_between_sends_min=c.delay_between_sends_min,
            delay_between_sends_max=c.delay_between_sends_max,
            delay_randomness_percent=c.delay_randomness_percent,
            spamblock_errors_to_skip=c.spamblock_errors_to_skip,
            messages_sent_today=c.messages_sent_today,
            total_messages_sent=c.total_messages_sent,
            total_recipients=c.total_recipients,
            accounts_count=acc_count_q.scalar() or 0,
            created_at=c.created_at, updated_at=c.updated_at,
        ))
    return TgCampaignListResponse(items=items, total=len(items))


@router.post("/campaigns", response_model=TgCampaignResponse)
async def create_campaign(data: TgCampaignCreate, session: AsyncSession = Depends(get_session)):
    campaign = TgCampaign(
        name=data.name, daily_message_limit=data.daily_message_limit,
        timezone=data.timezone, send_from_hour=data.send_from_hour, send_to_hour=data.send_to_hour,
        delay_between_sends_min=data.delay_between_sends_min,
        delay_between_sends_max=data.delay_between_sends_max,
        delay_randomness_percent=data.delay_randomness_percent,
        spamblock_errors_to_skip=data.spamblock_errors_to_skip,
    )
    session.add(campaign)
    await session.flush()
    # Auto-create empty sequence
    seq = TgSequence(campaign_id=campaign.id, name=f"{data.name} Sequence")
    session.add(seq)
    await session.flush()

    return TgCampaignResponse(
        id=campaign.id, name=campaign.name, status="draft",
        daily_message_limit=campaign.daily_message_limit,
        timezone=campaign.timezone, send_from_hour=campaign.send_from_hour,
        send_to_hour=campaign.send_to_hour,
        delay_between_sends_min=campaign.delay_between_sends_min,
        delay_between_sends_max=campaign.delay_between_sends_max,
        delay_randomness_percent=campaign.delay_randomness_percent,
        spamblock_errors_to_skip=campaign.spamblock_errors_to_skip,
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
        daily_message_limit=campaign.daily_message_limit,
        timezone=campaign.timezone, send_from_hour=campaign.send_from_hour,
        send_to_hour=campaign.send_to_hour,
        delay_between_sends_min=campaign.delay_between_sends_min,
        delay_between_sends_max=campaign.delay_between_sends_max,
        delay_randomness_percent=campaign.delay_randomness_percent,
        spamblock_errors_to_skip=campaign.spamblock_errors_to_skip,
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
    campaign.status = TgCampaignStatus.ACTIVE
    return {"ok": True, "status": "active"}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(TgCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    campaign.status = TgCampaignStatus.PAUSED
    return {"ok": True, "status": "paused"}


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

    # Remove existing
    existing = await session.execute(
        select(TgCampaignAccount).where(TgCampaignAccount.campaign_id == campaign_id)
    )
    for link in existing.scalars().all():
        await session.delete(link)

    # Add new
    for aid in account_ids:
        session.add(TgCampaignAccount(campaign_id=campaign_id, account_id=aid))

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

    added = 0
    for line in data.raw_text.strip().splitlines():
        username = line.strip().lstrip("@")
        if not username:
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

    campaign.total_recipients = (await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )).scalar() or 0

    return {"ok": True, "added": added, "total": campaign.total_recipients}


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

    added = 0
    for row in reader:
        username = row.get(mapping.username_column, "").strip().lstrip("@")
        if not username:
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

    campaign.total_recipients = (await session.execute(
        select(func.count(TgRecipient.id)).where(TgRecipient.campaign_id == campaign_id)
    )).scalar() or 0

    return {"ok": True, "added": added, "total": campaign.total_recipients}


@router.delete("/campaigns/{campaign_id}/recipients/{recipient_id}")
async def delete_recipient(campaign_id: int, recipient_id: int, session: AsyncSession = Depends(get_session)):
    recipient = await session.get(TgRecipient, recipient_id)
    if not recipient or recipient.campaign_id != campaign_id:
        raise HTTPException(404, "Recipient not found")
    await session.delete(recipient)
    return {"ok": True}


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
                variants=[
                    TgStepVariantSchema(
                        id=v.id, variant_label=v.variant_label,
                        message_text=v.message_text, weight_percent=v.weight_percent,
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
        )
        session.add(step)
        await session.flush()

        for v_data in step_data.variants:
            variant = TgStepVariant(
                step_id=step.id,
                variant_label=v_data.variant_label,
                message_text=v_data.message_text,
                weight_percent=v_data.weight_percent,
            )
            session.add(variant)

        new_steps.append(step)

    await session.flush()

    # Re-read and return
    return await get_sequence(campaign_id, session)


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
from app.services.telegram_engine import telegram_engine, TelegramEngine


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

    # Check for downloaded avatar
    photo_path = f"/app/tg_photos/{account.phone}.jpg"
    if os.path.exists(photo_path):
        return FileResponse(photo_path, media_type="image/jpeg")

    # Check profile_photo_path
    if account.profile_photo_path and os.path.exists(account.profile_photo_path):
        return FileResponse(account.profile_photo_path, media_type="image/jpeg")

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
    return {"ok": True, "session_file": account.phone}


# ── Auth flow ─────────────────────────────────────────────────────────

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
            account.status = TgAccountStatus.ACTIVE
            account.last_connected_at = func.now()

    return result


@router.post("/accounts/{account_id}/auth/verify-2fa")
async def auth_verify_2fa(account_id: int, password: str = Query(...),
                           session: AsyncSession = Depends(get_session)):
    result = await telegram_engine.verify_2fa(account_id, password)

    if result.get("status") == "authorized":
        account = await session.get(TgAccount, account_id)
        if account:
            account.status = TgAccountStatus.ACTIVE
            account.last_connected_at = func.now()

    return result


# ── Health check ──────────────────────────────────────────────────────

@router.post("/accounts/{account_id}/check")
async def check_account(account_id: int, session: AsyncSession = Depends(get_session)):
    account, proxy = await _get_account_with_proxy(account_id, session)

    if not telegram_engine.session_file_exists(account.phone):
        raise HTTPException(400, f"No session file for {account.phone}. Upload a .session file first.")

    kwargs = _account_connect_kwargs(account, proxy)
    result = await telegram_engine.check_account(account_id, **kwargs)

    # Update DB
    if result.get("authorized"):
        sb_map = {"none": TgSpamblockType.NONE, "temporary": TgSpamblockType.TEMPORARY,
                  "permanent": TgSpamblockType.PERMANENT}
        spamblock = sb_map.get(result.get("spamblock", "unknown"), account.spamblock_type)
        account.spamblock_type = spamblock
        account.status = TgAccountStatus.SPAMBLOCKED if spamblock != TgSpamblockType.NONE else TgAccountStatus.ACTIVE
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
                sb_map = {"none": TgSpamblockType.NONE, "temporary": TgSpamblockType.TEMPORARY,
                          "permanent": TgSpamblockType.PERMANENT}
                spamblock = sb_map.get(check.get("spamblock", "unknown"), account.spamblock_type)
                account.spamblock_type = spamblock
                account.status = TgAccountStatus.SPAMBLOCKED if spamblock != TgSpamblockType.NONE else TgAccountStatus.ACTIVE
                account.last_checked_at = func.now()
                account.last_connected_at = func.now()
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


@router.get("/crm/contacts")
async def list_crm_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    search: Optional[str] = None,
    campaign_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(TgContact)
    count_query = select(func.count(TgContact.id))

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
        "status": contact.status.value, "tags": contact.tags or [], "notes": contact.notes,
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


@router.get("/crm/stats")
async def crm_pipeline_stats(session: AsyncSession = Depends(get_session)):
    """Pipeline stats for CRM dashboard."""
    stats = {}
    for st in TgContactStatus:
        count = (await session.execute(
            select(func.count(TgContact.id)).where(TgContact.status == st)
        )).scalar() or 0
        stats[st.value] = count
    total = sum(stats.values())
    return {"total": total, **stats}


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
