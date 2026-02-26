"""Find duplicate SmartLead webhooks for monitored projects."""
import os, httpx, json, time
from sqlalchemy import create_engine, text

api_key = os.environ["SMARTLEAD_API_KEY"]
db_url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

engine = create_engine(db_url)
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT name, campaign_filters FROM projects "
        "WHERE deleted_at IS NULL AND webhooks_enabled = true"
    )).fetchall()
    all_filters = []
    for r in rows:
        name = r[0]
        filters = json.loads(r[1]) if r[1] else []
        all_filters.extend([f.lower() for f in filters if isinstance(f, str)])
        print(f"Project: {name} -> {len(filters)} campaign filters")

resp = httpx.get(
    "https://server.smartlead.ai/api/v1/campaigns",
    params={"api_key": api_key}, timeout=30
)
campaigns = resp.json() if isinstance(resp.json(), list) else []
active = [c for c in campaigns if str(c.get("status", "")).upper() == "ACTIVE"]

monitored_ids = set()
for camp in active:
    cname = (camp.get("name", "") or "").lower()
    if cname in all_filters:
        monitored_ids.add(camp.get("id"))

print(f"\nMonitored campaigns: {len(monitored_ids)} out of {len(active)} active")

correct_url = "http://46.62.210.24:8000/api/smartlead/webhook"
to_delete = []

for camp in active:
    cid = camp.get("id")
    if cid not in monitored_ids:
        continue
    cname = camp.get("name", "?")
    try:
        r = httpx.get(
            f"https://server.smartlead.ai/api/v1/campaigns/{cid}/webhooks",
            params={"api_key": api_key}, timeout=10
        )
        whs = r.json()
        if not isinstance(whs, list) or len(whs) <= 1:
            continue

        kept = False
        for wh in whs:
            wh_url = wh.get("webhook_url", "")
            wh_id = wh.get("id")
            wh_name = wh.get("name", "")
            if wh_url == correct_url and not kept:
                kept = True
                print(f"  KEEP [{cname}]: id={wh_id} name={wh_name}")
            else:
                to_delete.append(wh_id)

        if not kept:
            for wh in whs:
                wid = wh.get("id")
                if "46.62.210.24" in wh.get("webhook_url", ""):
                    to_delete.remove(wid)
                    print(f"  KEEP (fallback) [{cname}]: id={wid}")
                    break
        time.sleep(0.15)
    except Exception as e:
        print(f"  ERROR {cname}: {e}")

print(f"\nTotal webhooks to delete: {len(to_delete)}")
print(json.dumps(to_delete))
