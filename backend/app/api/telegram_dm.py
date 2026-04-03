"""Telegram DM Inbox API — account management, dialogs, messages."""
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.telegram_dm import TelegramDMAccount
from app.services.telegram_dm_service import telegram_dm_service

# Persistent storage for tdata archives (survives container restarts via volume)
TDATA_ARCHIVE_DIR = Path("/app/state/tdata_archives")
TDATA_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

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

@router.post("/accounts/upload-tdata/", response_model=list[AccountResponse])
async def upload_tdata(
    file: UploadFile = File(...),
    project_id: Optional[int] = Query(None, description="Auto-assign accounts to this project"),
    session: AsyncSession = Depends(get_session),
):
    """Import Telegram accounts from a tdata archive (ZIP or RAR).

    Supports multi-account tdata (up to 100 accounts per archive).
    Returns list of all imported accounts.
    """
    if not file.filename:
        raise HTTPException(400, "Upload a ZIP or RAR file containing the tdata folder")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("zip", "rar"):
        raise HTTPException(400, "Upload a ZIP or RAR file containing the tdata folder")

    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Import all accounts from tdata
        accounts_info = await telegram_dm_service.import_from_tdata(tmp.name)

        # Save archive persistently for future download
        if project_id:
            _save_project_archive(project_id, tmp.name, ext)

        results = []
        for info in accounts_info:
            # Check if account already exists
            existing = await session.execute(
                select(TelegramDMAccount).where(
                    TelegramDMAccount.telegram_user_id == info["telegram_user_id"]
                )
            )
            account = existing.scalar_one_or_none()

            if account:
                account.string_session = info["string_session"]
                account.username = info["username"]
                account.first_name = info["first_name"]
                account.last_name = info["last_name"]
                account.phone = info["phone"]
                account.auth_status = "active"
                account.last_error = None
                if project_id:
                    account.project_id = project_id
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
                    project_id=project_id,
                )
                session.add(account)

            await session.flush()

            # Connect
            ok = await telegram_dm_service.connect_account(
                account.id, info["string_session"]
            )
            account.is_connected = ok
            account.last_connected_at = datetime.utcnow() if ok else None
            results.append(account)

        await session.commit()
        return [_account_to_response(acc) for acc in results]

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"tdata import failed: {e}", exc_info=True)
        raise HTTPException(500, f"Import failed: {e}")
    finally:
        os.unlink(tmp.name)


@router.get("/projects/{project_id}/tdata-archive/")
async def check_tdata_archive(project_id: int):
    """Check if a tdata archive exists for this project."""
    archive = _find_project_archive(project_id)
    if archive:
        return {"exists": True, "filename": archive.name, "size": archive.stat().st_size}
    return {"exists": False}


@router.get("/projects/{project_id}/tdata-archive/download/")
async def download_tdata_archive(project_id: int):
    """Download the stored tdata archive for a project."""
    archive = _find_project_archive(project_id)
    if not archive:
        raise HTTPException(404, "No tdata archive stored for this project")
    return FileResponse(
        path=str(archive),
        filename=archive.name,
        media_type="application/octet-stream",
    )


def _find_project_archive(project_id: int) -> Optional[Path]:
    """Find stored tdata archive for a project."""
    for ext in ("rar", "zip"):
        path = TDATA_ARCHIVE_DIR / f"project_{project_id}.{ext}"
        if path.exists():
            return path
    return None


def _save_project_archive(project_id: int, source_path: str, ext: str):
    """Save uploaded archive persistently for future download."""
    dest = TDATA_ARCHIVE_DIR / f"project_{project_id}.{ext}"
    shutil.copy2(source_path, str(dest))
    logger.info(f"Saved tdata archive for project {project_id}: {dest}")


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

    # Resolve proxy: prefer dm_account.proxy_config, fallback to TgAccount.assigned_proxy
    proxy_cfg = account.proxy_config
    if not proxy_cfg and account.phone:
        from app.models.telegram_outreach import TgAccount, TgProxy
        proxy_result = await session.execute(
            select(TgProxy).join(TgAccount, TgAccount.assigned_proxy_id == TgProxy.id)
            .where(TgAccount.phone == account.phone, TgProxy.is_active.is_(True)).limit(1)
        )
        proxy = proxy_result.scalar_one_or_none()
        if proxy:
            proxy_cfg = {
                "type": proxy.protocol.value if proxy.protocol else "socks5",
                "host": proxy.host, "port": proxy.port,
                "username": proxy.username, "password": proxy.password,
            }
            logger.info(f"Connect proxy fallback: dm_account {account.id} ({account.phone}) ← {proxy.host}:{proxy.port}")

    try:
        ok = await telegram_dm_service.connect_account(
            account.id, account.string_session, proxy_cfg
        )
    except Exception as e:
        account.auth_status = "error"
        account.is_connected = False
        account.last_error = str(e)
        account.last_error_at = datetime.utcnow()
        await session.commit()
        raise HTTPException(400, f"Connection failed: {e}")

    account.is_connected = ok
    account.auth_status = "active" if ok else "error"
    account.last_connected_at = datetime.utcnow() if ok else account.last_connected_at
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
