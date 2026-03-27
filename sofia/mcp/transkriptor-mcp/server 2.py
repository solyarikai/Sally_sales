"""
Transkriptor MCP Server
Transcribes video/audio URLs and local files, returns markdown.
"""

import os
import time
import httpx
from fastmcp import FastMCP

API_KEY = os.environ.get("TRANSKRIPTOR_API_KEY", "")
BASE_URL = "https://api.tor.app/developer"

mcp = FastMCP("Transkriptor")


def headers():
    key = API_KEY or os.environ.get("TRANSKRIPTOR_API_KEY", "")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def poll(order_id: str, max_wait: int = 600) -> dict:
    """Poll until transcription status == Completed."""
    url = f"{BASE_URL}/files/{order_id}/content"
    for _ in range(max_wait // 5):
        resp = httpx.get(url, headers=headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")
        if status == "Completed":
            return data
        if status not in ("Processing", ""):
            raise RuntimeError(f"Unexpected status: {status}")
        time.sleep(5)
    raise TimeoutError(f"Transcription not ready after {max_wait}s")


def to_markdown(data: dict) -> str:
    """Convert Transkriptor content response to clean markdown."""
    file_name = data.get("file_name", "Transcription")
    language = data.get("language", "")
    content = data.get("content", [])

    lines = [f"# {file_name}", ""]
    if language:
        lines += [f"**Language:** {language}", ""]

    current_speaker = None
    buffer = []

    for segment in content:
        speaker = segment.get("speaker", "")
        text = (segment.get("text") or "").strip()
        if not text:
            continue

        if speaker and speaker != current_speaker:
            if buffer:
                lines.append(" ".join(buffer))
                buffer = []
            lines.append(f"\n**{speaker}:**")
            current_speaker = speaker

        buffer.append(text)

    if buffer:
        lines.append(" ".join(buffer))

    return "\n".join(lines).strip()


@mcp.tool()
def transcribe_url(
    url: str,
    language: str = "ru-RU",
    service: str = "Standard",
) -> str:
    """
    Transcribe video/audio from a public URL (YouTube, Google Drive, Dropbox, OneDrive).
    Returns transcription as markdown.

    Args:
        url: Public URL to the video/audio (e.g. YouTube link)
        language: ISO code, e.g. 'ru-RU', 'en-US'. Default: ru-RU
        service: 'Standard' (full text) or 'Subtitle' (with timestamps). Default: Standard
    """
    resp = httpx.post(
        f"{BASE_URL}/transcription/url",
        headers=headers(),
        json={"url": url, "language": language, "service": service},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json().get("body", resp.json())
    order_id = body["order_id"]

    data = poll(order_id)
    return to_markdown(data)


@mcp.tool()
def transcribe_file(
    file_path: str,
    language: str = "ru-RU",
    service: str = "Standard",
) -> str:
    """
    Transcribe a local video/audio file.
    Returns transcription as markdown.

    Args:
        file_path: Absolute path to the file (mp4, mp3, wav, m4a, etc.)
        language: ISO code, e.g. 'ru-RU', 'en-US'. Default: ru-RU
        service: 'Standard' or 'Subtitle'. Default: Standard
    """
    file_name = os.path.basename(file_path)

    # Step 1: Get presigned upload URL
    resp = httpx.post(
        f"{BASE_URL}/transcription/local_file/get_upload_url",
        headers=headers(),
        json={"file_name": file_name},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json().get("body", resp.json())
    upload_url = result["upload_url"]
    public_url = result["public_url"]

    # Step 2: Upload file to S3 presigned URL
    with open(file_path, "rb") as f:
        put_resp = httpx.put(upload_url, content=f, timeout=300)
        put_resp.raise_for_status()

    # Step 3: Initiate transcription
    resp = httpx.post(
        f"{BASE_URL}/transcription/local_file/initiate_transcription",
        headers=headers(),
        json={"url": public_url, "language": language, "service": service},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json().get("body", resp.json())
    order_id = body["order_id"]

    data = poll(order_id)
    return to_markdown(data)


@mcp.tool()
def check_balance() -> str:
    """Check remaining transcription minutes in the Transkriptor account."""
    resp = httpx.get(f"{BASE_URL}/users", headers=headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    minutes = data.get("minutes", "unknown")
    email = data.get("user_mail", "")
    return f"Account: {email}\nRemaining minutes: {minutes}"


if __name__ == "__main__":
    mcp.run()
