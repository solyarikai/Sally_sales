"""
iGaming LLM enrichment service.

Processes rows with AI prompts (Gemini / OpenAI) for custom column enrichment.
Supports batch processing with progress tracking.
"""
import asyncio
import json
import logging
from typing import Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.igaming import IGamingContact, IGamingCompany, IGamingAIColumn

logger = logging.getLogger(__name__)

# ── Progress tracking ─────────────────────────────────────────────────

_task_progress: dict[int, dict] = {}  # column_id -> {processed, total, status, errors}


def get_progress(column_id: int) -> dict:
    return _task_progress.get(column_id, {"processed": 0, "total": 0, "status": "idle", "errors": []})


# ── LLM adapters ──────────────────────────────────────────────────────

async def _call_gemini(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """Call Gemini API."""
    from app.services.gemini_client import gemini_generate
    result = await gemini_generate(
        system_prompt="You are a helpful data enrichment assistant. Respond concisely with just the answer, no explanations.",
        user_prompt=prompt,
        temperature=0.3,
        max_tokens=500,
        model=model,
    )
    return (result.get("content") or "").strip()


async def _call_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Call OpenAI API."""
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a helpful data enrichment assistant. Respond concisely with just the answer, no explanations."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()


async def call_llm(prompt: str, model: str) -> str:
    """Route to the right LLM based on model name."""
    if model.startswith("gemini"):
        return await _call_gemini(prompt, model)
    elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        return await _call_openai(prompt, model)
    else:
        # Default to Gemini Flash
        return await _call_gemini(prompt, "gemini-2.5-flash")


# ── Template rendering ────────────────────────────────────────────────

def render_prompt(template: str, row: dict) -> str:
    """
    Render prompt template with row data.
    Supports {field_name} placeholders.
    Example: "Describe {organization_name} ({website_url}) in 2 sentences"
    """
    result = template
    for key, value in row.items():
        placeholder = "{" + key + "}"
        if placeholder in result:
            result = result.replace(placeholder, str(value or ""))
    return result


# ── Main enrichment logic ─────────────────────────────────────────────

async def run_ai_column(
    session: AsyncSession,
    column_id: int,
    filter_params: Optional[dict] = None,
) -> dict:
    """
    Run AI enrichment for a column definition.
    Processes matching rows, calls LLM for each, stores result in custom_fields.

    Returns: {processed, errors, total}
    """
    # Load column definition
    col = (await session.execute(
        select(IGamingAIColumn).where(IGamingAIColumn.id == column_id)
    )).scalar_one_or_none()
    if not col:
        raise ValueError(f"AI column {column_id} not found")

    model = col.model
    prompt_template = col.prompt_template
    col_name = col.name
    target = col.target  # "contact" or "company"

    # Build query
    if target == "company":
        query = select(IGamingCompany)
        if filter_params:
            if filter_params.get("ids"):
                query = query.where(IGamingCompany.id.in_(filter_params["ids"]))
            if filter_params.get("has_website"):
                query = query.where(IGamingCompany.website.isnot(None))
    else:
        query = select(IGamingContact).where(IGamingContact.is_active == True)
        if filter_params:
            if filter_params.get("ids"):
                query = query.where(IGamingContact.id.in_(filter_params["ids"]))
            if filter_params.get("business_type"):
                query = query.where(IGamingContact.business_type == filter_params["business_type"])
            if filter_params.get("source_conference"):
                query = query.where(IGamingContact.source_conference == filter_params["source_conference"])

    rows = (await session.execute(query)).scalars().all()
    total = len(rows)

    # Update column status
    col.status = "running"
    col.rows_total = total
    col.rows_processed = 0
    await session.flush()

    _task_progress[column_id] = {"processed": 0, "total": total, "status": "running", "errors": []}

    processed = 0
    errors = []
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent LLM calls

    async def process_row(row):
        nonlocal processed
        async with semaphore:
            try:
                # Build row dict for template
                row_dict = {c.key: getattr(row, c.key) for c in row.__table__.columns}
                prompt = render_prompt(prompt_template, row_dict)

                # Skip if already enriched for this column
                existing = (row.custom_fields or {}).get(col_name)
                if existing:
                    processed += 1
                    return

                result = await call_llm(prompt, model)

                # Store in custom_fields
                cf = dict(row.custom_fields or {})
                cf[col_name] = result
                row.custom_fields = cf

                processed += 1
                _task_progress[column_id]["processed"] = processed

                if processed % 10 == 0:
                    await session.flush()
                    logger.info(f"AI column '{col_name}': {processed}/{total}")

            except Exception as e:
                errors.append({"id": row.id, "error": str(e)})
                _task_progress[column_id]["errors"] = errors[-10:]  # Keep last 10
                logger.warning(f"AI column error for row {row.id}: {e}")

    # Process in batches
    batch_size = 20
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        await asyncio.gather(*[process_row(r) for r in batch])
        await session.flush()

    # Update column status
    col.status = "completed"
    col.rows_processed = processed
    await session.flush()

    _task_progress[column_id] = {"processed": processed, "total": total, "status": "completed", "errors": errors[-10:]}

    logger.info(f"AI column '{col_name}' done: {processed}/{total} processed, {len(errors)} errors")
    return {"processed": processed, "total": total, "errors": len(errors)}
