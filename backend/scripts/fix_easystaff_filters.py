"""Fix easystaff ru campaign_filters: keep only Russian campaigns."""
import asyncio
import json
from app.db import async_session_maker
from sqlalchemy import text


def is_russian_campaign(name: str) -> bool:
    """Campaign belongs to EasyStaff RU if it explicitly targets Russian market."""
    lower = name.lower()
    # Keep: contains "russian", " ru ", " ru-", starts with "easystaff ru"
    if "russian" in lower:
        return True
    if lower.startswith("easystaff ru"):
        return True
    if " ru " in lower or " ru-" in lower or lower.endswith(" ru"):
        return True
    # Keep: Russian DM campaigns
    if "russian dm" in lower:
        return True
    # Keep: Sigma (active EasyStaff RU SmartLead campaign)
    if "sigma" in lower and "easystaff" in lower:
        return True
    return False


async def main():
    async with async_session_maker() as s:
        r = await s.execute(text("SELECT campaign_filters FROM projects WHERE id = 40"))
        current = r.scalar() or []
        print(f"Current: {len(current)} filters")

        keep = []
        remove = []
        for f in current:
            if is_russian_campaign(f):
                keep.append(f)
            else:
                remove.append(f)

        print(f"\nKEEPING ({len(keep)}):")
        for f in sorted(keep):
            print(f"  + {f}")

        print(f"\nREMOVING ({len(remove)}):")
        for f in sorted(remove):
            print(f"  - {f}")

        # Update
        filters_json = json.dumps(sorted(keep))
        await s.execute(text(
            "UPDATE projects SET campaign_filters = CAST(:filters AS jsonb) WHERE id = :pid"
        ), {"filters": filters_json, "pid": 40})
        await s.commit()
        print(f"\nDone! Updated to {len(keep)} filters")


asyncio.run(main())
