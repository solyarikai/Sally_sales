import requests, os, json
API_KEY = os.environ["SMARTLEAD_API_KEY"]
r = requests.get("https://server.smartlead.ai/api/v1/campaigns", params={"api_key": API_KEY})
data = r.json()
print(type(data), str(data)[:200])
if isinstance(data, list):
    campaigns = data
elif isinstance(data, dict):
    campaigns = data.get("data", data.get("campaigns", []))
else:
    campaigns = []

print(f"Total: {len(campaigns)}")
for c in campaigns:
    if not isinstance(c, dict):
        continue
    name = c.get("name", "")
    if any(k in name.upper() for k in ["AGENC", "IM-FIRST", "IMAGENCY"]):
        print(f"{c.get('id'):>10} | {c.get('status','?'):>12} | {name}")
