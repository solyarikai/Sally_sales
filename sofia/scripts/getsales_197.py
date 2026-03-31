import json, csv

with open("/home/leadokol/magnum-opus-project/repo/gathering-data/onsocial_infplat_v4_people_enriched.json") as f:
    data = json.load(f)

no_email = [p for p in data if not p.get("email") or not p["email"].strip()]
print(f"No email contacts: {len(no_email)}")

GS_HEADERS = ["system_uuid","pipeline_stage","full_name","first_name","last_name","position","headline","about","linkedin_id","sales_navigator_id","linkedin_nickname","linkedin_url","facebook_nickname","twitter_nickname","work_email","personal_email","work_phone","personal_phone","connections_number","followers_number","primary_language","has_open_profile","has_verified_profile","has_premium","location_country","location_state","location_city","active_flows","list_name","tags","company_name","company_industry","company_linkedin_id","company_domain","company_linkedin_url","company_employees_range","company_headquarter","cf_location","cf_competitor_client","cf_message1","cf_message2","cf_message3","cf_personalization","cf_compersonalization","cf_personalization1","cf_message4","cf_linkedin_personalization","cf_subject","created_at"]

outpath = "/tmp/getsales_infplat_v4_apollo_noemail_197.csv"
with open(outpath, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=GS_HEADERS, extrasaction="ignore")
    w.writeheader()
    for p in no_email:
        ln = p.get("linkedin_url", "")
        nick = ln.rstrip("/").split("/")[-1] if ln else ""
        first = p.get("first_name", "")
        last = p.get("last_name", "")
        row = {h: "" for h in GS_HEADERS}
        row["full_name"] = (first + " " + last).strip()
        row["first_name"] = first
        row["last_name"] = last
        row["position"] = p.get("title", "")
        row["linkedin_nickname"] = nick
        row["linkedin_url"] = ln
        row["location_country"] = p.get("country", "")
        row["location_city"] = p.get("city", "")
        row["list_name"] = "OnSocial INFPLAT v4 Apollo No Email - 2026-03-31"
        row["tags"] = "INFLUENCER_PLATFORMS"
        row["company_name"] = p.get("company_name", "")
        row["company_domain"] = p.get("domain", "")
        row["cf_location"] = p.get("country", "")
        row["cf_competitor_client"] = p.get("social_proof", "")
        w.writerow(row)

print(f"Written: {len(no_email)} rows to {outpath}")
