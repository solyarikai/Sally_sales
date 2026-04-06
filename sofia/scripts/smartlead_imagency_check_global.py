import requests, os, json

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"

r = requests.get(f"{BASE}/campaigns/3050462/sequences", params={"api_key": API_KEY})
steps = r.json()

print(json.dumps(steps, indent=2))
