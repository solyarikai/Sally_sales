"""Telegram DM Inbox API — account management, dialogs, messages."""
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.telegram_dm import TelegramDMAccount
from app.services.telegram_dm_service import telegram_dm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram-dm", tags=["telegram-dm"])


# ── Schemas ─────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    id: int
    phone: Optional[str] = None
    telegram_user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    auth_status: str
    is_connected: bool
    project_id: Optional[int] = None
    last_connected_at: Optional[str] = None
    last_error: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    text: str


class UpdateAccountRequest(BaseModel):
    project_id: Optional[int] = None


# ── Account Management ──────────────────────────────────────────────

@router.post("/accounts/upload-tdata/", response_model=AccountResponse)
async def upload_tdata(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Import a Telegram account from a tdata ZIP archive."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Upload a ZIP file containing the tdata folder")

    # Save uploaded file to temp
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Import
        info = await telegram_dm_service.import_from_tdata(tmp.name)

        # Check if account already exists
        existing = await session.execute(
            select(TelegramDMAccount).where(
                TelegramDMAccount.telegram_user_id == info["telegram_user_id"]
            )
        )
        account = existing.scalar_one_or_none()

        if account:
            # Update existing account with new session
            account.string_session = info["string_session"]
            account.username = info["username"]
            account.first_name = info["first_name"]
            account.last_name = info["last_name"]
            account.phone = info["phone"]
            account.auth_status = "active"
            account.last_error = None
        else:
            account = TelegramDMAccount(
                telegram_user_id=info["telegram_user_id"],
                username=info["username"],
                first_name=info["first_name"],
                last_name=info["last_name"],
                phone=info["phone"],
                string_session=info["string_session"],
                auth_status="active",
                company_id=1,
            )
            session.add(account)

        await session.flush()

        # Connect
        ok = await telegram_dm_service.connect_account(
            account.id, info["string_session"]
        )
        account.is_connected = ok
        account.last_connected_at = datetime.now(timezone.utc) if ok else None
        await session.commit()

        return _account_to_response(account)

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"tdata import failed: {e}")
        raise HTTPException(500, f"Import failed: {e}")
    finally:
        os.unlink(tmp.name)


@router.get("/accounts/", response_model=list[AccountResponse])
async def list_accounts(session: AsyncSession = Depends(get_session)):
    """List all Telegram DM accounts."""
    result = await session.execute(
        select(TelegramDMAccount).order_by(TelegramDMAccount.created_at.desc())
    )
    accounts = result.scalars().all()
    # Update is_connected from live service state
    for acc in accounts:
        acc.is_connected = telegram_dm_service.is_connected(acc.id)
    return [_account_to_response(acc) for acc in accounts]


@router.post("/accounts/{account_id}/connect/", response_model=AccountResponse)
async def connect_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Reconnect a previously authenticated account."""
    account = await _get_account(session, account_id)
    if not account.string_session:
        raise HTTPException(400, "No saved session. Re-upload tdata.")

    try:
        ok = await telegram_dm_service.connect_account(
            account.id, account.string_session, account.proxy_config
        )
    except Exception as e:
        account.auth_status = "error"
        account.is_connected = False
        account.last_error = str(e)
        account.last_error_at = datetime.now(timezone.utc)
        await session.commit()
        raise HTTPException(400, f"Connection failed: {e}")

    account.is_connected = ok
    account.auth_status = "active" if ok else "error"
    account.last_connected_at = datetime.now(timezone.utc) if ok else account.last_connected_at
    await session.commit()
    return _account_to_response(account)


@router.post("/accounts/{account_id}/disconnect/", response_model=AccountResponse)
async def disconnect_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Disconnect an account."""
    account = await _get_account(session, account_id)
    await telegram_dm_service.disconnect_account(account_id)
    account.is_connected = False
    account.auth_status = "disconnected"
    await session.commit()
    return _account_to_response(account)


@router.delete("/accounts/{account_id}/")
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove an account completely."""
    account = await _get_account(session, account_id)
    await telegram_dm_service.disconnect_account(account_id)
    await session.delete(account)
    await session.commit()
    return {"status": "deleted", "account_id": account_id}


@router.patch("/accounts/{account_id}/", response_model=AccountResponse)
async def update_account(
    account_id: int,
    body: UpdateAccountRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update account settings (project assignment)."""
    account = await _get_account(session, account_id)
    if body.project_id is not None:
        account.project_id = body.project_id or None
    await session.commit()
    return _account_to_response(account)


# ── Dialogs & Messages ─────────────────────────────────────────────

@router.get("/accounts/{account_id}/dialogs/")
async def get_dialogs(
    account_id: int,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List recent DM conversations for an account."""
    await _get_account(session, account_id)  # verify exists
    try:
        return await telegram_dm_service.get_dialogs(account_id, limit)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch dialogs: {e}")


@router.get("/accounts/{account_id}/messages/{peer_id}/")
async def get_messages(
    account_id: int,
    peer_id: int,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Fetch conversation thread with a specific peer."""
    await _get_account(session, account_id)
    try:
        return await telegram_dm_service.get_messages(account_id, peer_id, limit)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch messages: {e}")


@router.post("/accounts/{account_id}/messages/{peer_id}/")
async def send_message(
    account_id: int,
    peer_id: int,
    body: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
):
    """Send a Telegram DM."""
    await _get_account(session, account_id)
    result = await telegram_dm_service.send_message(account_id, peer_id, body.text)
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Send failed"))
    return result


# ── Helpers ─────────────────────────────────────────────────────────

async def _get_account(session: AsyncSession, account_id: int) -> TelegramDMAccount:
    result = await session.execute(
        select(TelegramDMAccount).where(TelegramDMAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, f"Account {account_id} not found")
    return account


def _account_to_response(acc: TelegramDMAccount) -> AccountResponse:
    return AccountResponse(
        id=acc.id,
        phone=acc.phone,
        telegram_user_id=acc.telegram_user_id,
        username=acc.username,
        first_name=acc.first_name,
        last_name=acc.last_name,
        auth_status=acc.auth_status,
        is_connected=acc.is_connected,
        project_id=acc.project_id,
        last_connected_at=acc.last_connected_at.isoformat() if acc.last_connected_at else None,
        last_error=acc.last_error,
        created_at=acc.created_at.isoformat() if acc.created_at else None,
    )
