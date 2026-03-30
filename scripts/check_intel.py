import urllib.request, json

r = urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8000/api/intelligence/?project_id=48&page_size=15&sort_by=warmth_desc",
    headers={"X-Company-ID": "1"}
))
items = json.loads(r.read())
for it in items:
    nm = (it.get("lead_name") or "")[:30].ljust(30)
    ints = (it.get("interests") or "(none)")[:140]
    tags = it.get("tags") or []
    geo = it.get("geo_tags") or []
    print(f"ID={it['id']} | {nm} | {it['intent']:20s} | offer={it['offer_responded_to'] or 'general':8s} | W={it['warmth_score']}")
    print(f"  interests: {ints}")
    print(f"  tags: {tags}")
    print(f"  geo:  {geo}")
    print()
