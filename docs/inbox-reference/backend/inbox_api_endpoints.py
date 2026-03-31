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
    """List telegram_dm_accounts available for inbox."""
    result = await session.execute(
        select(TelegramDMAccount).where(
            TelegramDMAccount.string_session.isnot(None)
        ).order_by(TelegramDMAccount.id)
    )
    accounts = result.scalars().all()
    return [{"id": a.id, "phone": a.phone, "username": a.username, "first_name": a.first_name, "is_connected": a.is_connected, "auth_status": a.auth_status} for a in accounts]


@router.get("/inbox/dialogs")
async def list_inbox_dialogs(
    account_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    campaign_tag: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List cached dialogs. At least one filter required."""
    if not account_id and not campaign_id and not campaign_tag and not tag:
        raise HTTPException(400, "Select at least one filter: account, campaign, campaign tag, or tag")

    query = select(TgInboxDialog).order_by(TgInboxDialog.last_message_at.desc().nullslast())
    count_q = select(func.count(TgInboxDialog.id))

    if account_id:
        query = query.where(TgInboxDialog.account_id == account_id)
        count_q = count_q.where(TgInboxDialog.account_id == account_id)
    if campaign_id:
        query = query.where(TgInboxDialog.campaign_id == campaign_id)
        count_q = count_q.where(TgInboxDialog.campaign_id == campaign_id)
    if campaign_tag:
        # Join with TgCampaign to filter by tag
        query = query.join(TgCampaign, TgInboxDialog.campaign_id == TgCampaign.id).where(
            TgCampaign.tags.op("@>")(f'["{campaign_tag}"]')
        )
        count_q = count_q.join(TgCampaign, TgInboxDialog.campaign_id == TgCampaign.id).where(
            TgCampaign.tags.op("@>")(f'["{campaign_tag}"]')
        )
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

    total = (await session.execute(count_q)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    dialogs = result.scalars().all()

    # Get account info from telegram_dm_accounts for each dialog
    account_cache = {}
    items = []
    for d in dialogs:
        if d.account_id not in account_cache:
            acc = await session.get(TelegramDMAccount, d.account_id)
            account_cache[d.account_id] = acc
        acc = account_cache[d.account_id]

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
    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    account = await session.get(TelegramDMAccount, dialog.account_id)
    if not account:
        raise HTTPException(404, "Account not found in telegram_dm_accounts")
    if not account.string_session:
        raise HTTPException(400, "Account has no string_session")

    # Check if already connected — avoid disconnect at the end if so
    already_connected = telegram_dm_service.is_connected(dialog.account_id)

    try:
        if not already_connected:
            ok = await telegram_dm_service.connect_account(dialog.account_id, account.string_session, account.proxy_config)
            if not ok:
                raise HTTPException(500, "Failed to connect account")

        messages = await telegram_dm_service.get_messages(dialog.account_id, dialog.peer_id, limit=limit)

        # Map field names to match existing frontend expectations
        formatted = []
        for m in messages:
            formatted.append({
                "id": m["id"],
                "direction": m["direction"],
                "text": m["text"],
                "timestamp": m.get("sent_at"),
            })

        if not already_connected:
            await telegram_dm_service.disconnect_account(dialog.account_id)

        return {
            "messages": formatted,
            "peer_name": dialog.peer_name,
            "peer_username": dialog.peer_username,
            "account_phone": account.phone,
            "campaign_id": dialog.campaign_id,
            "tag": dialog.inbox_tag,
        }
    except HTTPException:
        raise
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(dialog.account_id)
        except:
            pass
        raise HTTPException(500, f"Failed to fetch messages: {str(e)[:100]}")


@router.post("/inbox/dialogs/{dialog_id}/send")
async def send_dialog_message(
    dialog_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Send a message in a dialog via telegram_dm_service."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Message text required")

    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    account = await session.get(TelegramDMAccount, dialog.account_id)
    if not account or account.auth_status != "active":
        raise HTTPException(400, "Account not active")
    if not account.string_session:
        raise HTTPException(400, "Account has no string_session")

    # Check if already connected — avoid disconnect at the end if so
    already_connected = telegram_dm_service.is_connected(dialog.account_id)

    try:
        if not already_connected:
            ok = await telegram_dm_service.connect_account(dialog.account_id, account.string_session, account.proxy_config)
            if not ok:
                raise HTTPException(500, "Failed to connect account")

        result = await telegram_dm_service.send_message(dialog.account_id, dialog.peer_id, text)

        if not already_connected:
            await telegram_dm_service.disconnect_account(dialog.account_id)

        if result.get("success"):
            # Update dialog cache
            dialog.last_message_text = text[:500]
            dialog.last_message_at = datetime.utcnow()
            dialog.last_message_outbound = True
            await session.commit()

        return result
    except HTTPException:
        raise
    except Exception as e:
        try:
            if not already_connected:
                await telegram_dm_service.disconnect_account(dialog.account_id)
        except:
            pass
        raise HTTPException(500, f"Send failed: {str(e)[:100]}")


@router.patch("/inbox/dialogs/{dialog_id}/tag")
async def tag_dialog(
    dialog_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Tag an inbox dialog."""
    tag = body.get("tag", "")
    if tag and tag not in ("interested", "info_requested", "not_interested"):
        raise HTTPException(400, "Invalid tag")

    dialog = await session.get(TgInboxDialog, dialog_id)
    if not dialog:
        raise HTTPException(404, "Dialog not found")

    dialog.inbox_tag = tag or None
    await session.commit()
    return {"ok": True}


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
