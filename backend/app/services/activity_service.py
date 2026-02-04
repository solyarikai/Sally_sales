"""Activity service with deduplication support."""
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from app.models.contact import ContactActivity


async def add_activity_dedup(
    session,
    contact_id: int,
    activity_type: str,
    channel: str,
    source: str,
    activity_at: datetime,
    snippet: str = None,
    **kwargs
) -> ContactActivity | None:
    """
    Add activity with deduplication.
    Returns the activity if created, None if duplicate.
    """
    # For reply activities, check for existing within same minute
    if 'replied' in activity_type:
        minute_start = activity_at.replace(second=0, microsecond=0)
        minute_end = minute_start.replace(second=59, microsecond=999999)
        
        existing = await session.execute(
            select(ContactActivity).where(
                ContactActivity.contact_id == contact_id,
                ContactActivity.source == source,
                ContactActivity.activity_type == activity_type,
                ContactActivity.activity_at >= minute_start,
                ContactActivity.activity_at <= minute_end,
                ContactActivity.snippet == snippet
            )
        )
        if existing.scalar():
            return None  # Duplicate found
    
    activity = ContactActivity(
        contact_id=contact_id,
        activity_type=activity_type,
        channel=channel,
        source=source,
        activity_at=activity_at,
        snippet=snippet,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **kwargs
    )
    session.add(activity)
    return activity
