import requests, os, json

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"

# Fetch sequences from Global (best rate 0.92%) and Europe (most replies 12, 7 from thread)
for cid, name in [(3050462, "Global"), (3064335, "Europe")]:
    print(f"\n{'='*60}")
    print(f"{name} ({cid})")
    r = requests.get(f"{BASE}/campaigns/{cid}/sequences", params={"api_key": API_KEY})
    steps = r.json()
    for s in steps:
        num = s.get("seq_number")
        day = s.get("seq_delay_details", {}).get("delay_in_days") or s.get("seq_delay_details", {}).get("delayInDays", "?")
        variants = s.get("seq_variants", [])
        print(f"\n--- Step {num} (day={day}) ---")
        if variants:
            for v in variants:
                print(f"  [variant] subj: {v.get('subject','')!r}")
                print(f"  body: {v.get('email_body','')}")
        else:
            print(f"  subj: {s.get('subject','')!r}")
            print(f"  body: {s.get('email_body','')}")
