"""
Telegram Account Manager — handles multi-format import and session conversion.

Supported formats:
  - JSON + .session pairs (TeleRaptor native format)
  - TDATA folders (Telegram Desktop)
  - Standalone .session files (Telethon)

Conversion:
  - session → tdata (via opentele)
  - tdata → session (via opentele)
"""
import asyncio
import json
import logging
import os
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(os.environ.get("TG_SESSIONS_DIR", "/app/tg_sessions"))
TDATA_DIR = Path(os.environ.get("TG_TDATA_DIR", "/app/tg_tdata"))
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
TDATA_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════
# File parsing helpers
# ══════════════════════════════════════════════════════════════════════

def parse_teleraptor_json(data: bytes) -> Optional[dict]:
    """Parse a TeleRaptor .json account file."""
    try:
        obj = json.loads(data)
        if isinstance(obj, dict) and obj.get("phone"):
            return obj
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return None


def match_json_session_pairs(files: dict[str, bytes]) -> list[dict]:
    """
    Match .json and .session files by basename (phone number).
    Returns list of {json_data: dict, session_bytes: bytes, phone: str}.
    """
    jsons = {}
    sessions = {}

    for name, content in files.items():
        basename = Path(name).stem
        ext = Path(name).suffix.lower()
        if ext == ".json":
            parsed = parse_teleraptor_json(content)
            if parsed:
                jsons[basename] = parsed
        elif ext == ".session":
            sessions[basename] = content

    results = []
    # Match by basename (phone number)
    for basename, json_data in jsons.items():
        phone = json_data.get("phone", basename)
        session_bytes = sessions.get(basename) or sessions.get(phone)
        results.append({
            "json_data": json_data,
            "session_bytes": session_bytes,
            "phone": phone,
            "has_session": session_bytes is not None,
        })

    # Standalone sessions without JSON
    matched_session_keys = set()
    for basename in jsons:
        phone = jsons[basename].get("phone", basename)
        if basename in sessions:
            matched_session_keys.add(basename)
        if phone in sessions:
            matched_session_keys.add(phone)

    for basename, session_bytes in sessions.items():
        if basename not in matched_session_keys:
            results.append({
                "json_data": {"phone": basename},
                "session_bytes": session_bytes,
                "phone": basename,
                "has_session": True,
            })

    return results


def extract_files_from_upload(files_data: list[tuple[str, bytes]]) -> dict[str, bytes]:
    """
    From a list of (filename, content) pairs, extract all files.
    If a file is a .zip, extract its contents.
    """
    result = {}
    for name, content in files_data:
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(BytesIO(content)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        fname = Path(info.filename).name
                        if fname.startswith(".") or fname.startswith("__"):
                            continue
                        result[fname] = zf.read(info)
            except zipfile.BadZipFile:
                logger.warning(f"Bad zip file: {name}")
        else:
            result[name] = content
    return result


def detect_tdata_in_files(files: dict[str, bytes]) -> Optional[dict[str, bytes]]:
    """Check if uploaded files contain a tdata structure."""
    tdata_markers = {"key_datas", "key_data", "D877F783D5D3EF8C"}
    for name in files:
        basename = Path(name).stem
        if basename in tdata_markers or "tdata" in name.lower():
            return files
    return None


# ══════════════════════════════════════════════════════════════════════
# Session storage
# ══════════════════════════════════════════════════════════════════════

def save_session_file(phone: str, content: bytes) -> Path:
    """Save a .session file to the sessions directory."""
    path = SESSIONS_DIR / f"{phone}.session"
    path.write_bytes(content)
    logger.info(f"Session saved: {path}")
    return path


def get_session_path(phone: str) -> Optional[Path]:
    """Get path to session file if it exists."""
    path = SESSIONS_DIR / f"{phone}.session"
    return path if path.exists() else None


def save_tdata_folder(phone: str, files: dict[str, bytes]) -> Path:
    """Save tdata files for an account."""
    tdata_path = TDATA_DIR / phone
    tdata_path.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (tdata_path / name).write_bytes(content)
    logger.info(f"TDATA saved: {tdata_path}")
    return tdata_path


# ══════════════════════════════════════════════════════════════════════
# Conversion (opentele)
# ══════════════════════════════════════════════════════════════════════

async def convert_session_to_tdata(phone: str, api_id: int = 2040, api_hash: str = "b18441a1ff607e10a989891a5462e627") -> Optional[Path]:
    """
    Convert a Telethon .session file to tdata format.
    Returns path to tdata folder.
    """
    session_path = get_session_path(phone)
    if not session_path:
        raise FileNotFoundError(f"Session file not found for {phone}")

    try:
        from opentele.tl import TelegramClient as OTClient
        from opentele.api import UseCurrentSession

        output_dir = TDATA_DIR / phone
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run in thread to avoid blocking
        def _convert():
            client = OTClient(str(session_path.with_suffix("")))
            tdata = client.ToTDesktop(
                flag=UseCurrentSession,
            )
            tdata.SaveTData(str(output_dir))
            return output_dir

        result = await asyncio.to_thread(_convert)
        logger.info(f"Converted session → tdata for {phone}: {result}")
        return result

    except ImportError:
        logger.error("opentele not installed — cannot convert session to tdata")
        raise RuntimeError("opentele not installed. Run: pip install opentele")
    except Exception as e:
        logger.error(f"Session → tdata conversion failed for {phone}: {e}")
        raise


async def convert_tdata_to_session(phone: str, api_id: int = 2040, api_hash: str = "b18441a1ff607e10a989891a5462e627") -> Optional[Path]:
    """
    Convert a tdata folder to Telethon .session file.
    Returns path to .session file.
    """
    tdata_path = TDATA_DIR / phone
    if not tdata_path.exists():
        raise FileNotFoundError(f"TDATA folder not found for {phone}")

    try:
        from opentele.td import TDesktop
        from opentele.api import UseCurrentSession

        output_session = SESSIONS_DIR / phone

        def _convert():
            tdesk = TDesktop(str(tdata_path))
            client = tdesk.ToTelethon(
                session=str(output_session),
                flag=UseCurrentSession,
            )
            return output_session.with_suffix(".session")

        result = await asyncio.to_thread(_convert)
        logger.info(f"Converted tdata → session for {phone}: {result}")
        return result

    except ImportError:
        logger.error("opentele not installed — cannot convert tdata to session")
        raise RuntimeError("opentele not installed. Run: pip install opentele")
    except Exception as e:
        logger.error(f"TDATA → session conversion failed for {phone}: {e}")
        raise


async def package_tdata_as_zip(phone: str) -> bytes:
    """Package a tdata folder as a ZIP for download."""
    tdata_path = TDATA_DIR / phone
    if not tdata_path.exists():
        raise FileNotFoundError(f"No tdata for {phone}")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(tdata_path):
            for f in files:
                filepath = Path(root) / f
                arcname = filepath.relative_to(tdata_path)
                zf.write(filepath, arcname)
    return buf.getvalue()
