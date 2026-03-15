#!/usr/bin/env python3
"""Import GetSales CSV exports into contacts table via staging + upsert."""
import csv
import glob
import os
import subprocess
import sys

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'getsales_exports')
CLEAN_CSV = '/tmp/getsales_clean.csv'
EXPECTED_COLS = 49

def psql(sql, timeout=1800):
    """Run SQL via docker exec psql."""
    r = subprocess.run(
        ['docker', 'exec', '-i', 'leadgen-postgres', 'psql', '-U', 'leadgen', '-d', 'leadgen'],
        input=sql, capture_output=True, text=True, timeout=timeout
    )
    if r.stderr.strip():
        for line in r.stderr.strip().split('\n'):
            if not line.startswith('NOTICE:'):
                print(f"  ERR: {line}")
    if r.stdout.strip():
        print(r.stdout.strip())
    return r

def main():
    print("=== GetSales CSV Import ===")

    # Step 1: Read all CSVs
    print("Step 1: Reading CSVs...")
    csv_files = sorted(glob.glob(os.path.join(EXPORT_DIR, 'contacts_export_*.csv')))
    print("  Found {} CSV files".format(len(csv_files)))

    all_rows = []
    skipped = 0
    for f in csv_files:
        with open(f, 'r', encoding='utf-8', errors='replace') as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header:
                continue
            for row in reader:
                if len(row) >= EXPECTED_COLS:
                    cleaned = [cell.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').replace('\x00', '')
                              for cell in row[:EXPECTED_COLS]]
                    all_rows.append(cleaned)
                else:
                    skipped += 1

    print("  Loaded: {} rows ({} skipped)".format(len(all_rows), skipped))

    # Step 2: Write clean CSV
    print("Step 2: Writing clean CSV...")
    header_names = [
        'system_uuid','pipeline_stage','full_name','first_name','last_name',
        'position','headline','about','linkedin_id','sales_navigator_id',
        'linkedin_nickname','linkedin_url','facebook_nickname','twitter_nickname',
        'work_email','personal_email','work_phone','personal_phone',
        'connections_number','followers_number','primary_language',
        'has_open_profile','has_verified_profile','has_premium',
        'location_country','location_state','location_city',
        'active_flows','list_name','tags',
        'company_name','company_industry','company_linkedin_id','company_domain',
        'company_linkedin_url','company_employees_range','company_headquarter',
        'cf_location','cf_competitor_client','cf_message1','cf_message2','cf_message3',
        'cf_personalization','cf_compersonalization','cf_personalization1',
        'cf_message4','cf_linkedin_personalization','cf_subject','created_at'
    ]
    with open(CLEAN_CSV, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(header_names)
        for row in all_rows:
            writer.writerow(row)

    sz = os.path.getsize(CLEAN_CSV)
    print("  Clean CSV: {:.1f} MB, {} rows".format(sz / 1024 / 1024, len(all_rows)))

    # Step 3: Create staging table
    print("Step 3: Creating staging table...")
    psql("""
DROP TABLE IF EXISTS gs_import_staging;
CREATE TABLE gs_import_staging (
  system_uuid TEXT, pipeline_stage TEXT, full_name TEXT, first_name TEXT, last_name TEXT,
  position TEXT, headline TEXT, about TEXT, linkedin_id TEXT, sales_navigator_id TEXT,
  linkedin_nickname TEXT, linkedin_url TEXT, facebook_nickname TEXT, twitter_nickname TEXT,
  work_email TEXT, personal_email TEXT, work_phone TEXT, personal_phone TEXT,
  connections_number TEXT, followers_number TEXT, primary_language TEXT,
  has_open_profile TEXT, has_verified_profile TEXT, has_premium TEXT,
  location_country TEXT, location_state TEXT, location_city TEXT,
  active_flows TEXT, list_name TEXT, tags TEXT,
  company_name TEXT, company_industry TEXT, company_linkedin_id TEXT, company_domain TEXT,
  company_linkedin_url TEXT, company_employees_range TEXT, company_headquarter TEXT,
  cf_location TEXT, cf_competitor_client TEXT, cf_message1 TEXT, cf_message2 TEXT, cf_message3 TEXT,
  cf_personalization TEXT, cf_compersonalization TEXT, cf_personalization1 TEXT,
  cf_message4 TEXT, cf_linkedin_personalization TEXT, cf_subject TEXT, created_at TEXT
);
""")

    # Step 4: Copy file into Docker container, then use server-side COPY
    print("Step 4: Loading into staging...")
    subprocess.run(['docker', 'cp', CLEAN_CSV, 'leadgen-postgres:/tmp/getsales_clean.csv'], check=True)
    r = psql("COPY gs_import_staging FROM '/tmp/getsales_clean.csv' WITH (FORMAT csv, HEADER true, QUOTE '\"', ESCAPE '\"');")

    psql("SELECT COUNT(*) AS staging_rows FROM gs_import_staging;")

    # Step 5: Dedup staging
    print("Step 5: Deduplicating...")
    psql("""
DELETE FROM gs_import_staging a USING gs_import_staging b
WHERE a.ctid > b.ctid AND a.system_uuid = b.system_uuid
  AND a.system_uuid IS NOT NULL AND a.system_uuid != '';
""")
    psql("SELECT COUNT(*) AS unique_rows FROM gs_import_staging;")

    # Step 5b: Create indexes on staging for fast joins
    print("Step 5b: Creating indexes on staging...")
    psql("CREATE INDEX idx_staging_uuid ON gs_import_staging(system_uuid);")
    psql("CREATE INDEX idx_staging_work_email ON gs_import_staging(LOWER(work_email)) WHERE work_email IS NOT NULL AND work_email != '';")
    psql("CREATE INDEX idx_staging_personal_email ON gs_import_staging(LOWER(personal_email)) WHERE personal_email IS NOT NULL AND personal_email != '';")
    psql("CREATE INDEX idx_staging_linkedin ON gs_import_staging(linkedin_url) WHERE linkedin_url IS NOT NULL AND linkedin_url != '';")

    # Step 6: Upsert
    print("Step 6a: Update by getsales_id...")
    psql("""
WITH ups AS (
  UPDATE contacts c SET
    first_name = COALESCE(NULLIF(s.first_name,''), c.first_name),
    last_name = COALESCE(NULLIF(s.last_name,''), c.last_name),
    company_name = COALESCE(NULLIF(s.company_name,''), c.company_name),
    job_title = COALESCE(NULLIF(s.position,''), c.job_title),
    phone = COALESCE(NULLIF(s.work_phone,''), NULLIF(s.personal_phone,''), c.phone),
    linkedin_url = COALESCE(NULLIF(s.linkedin_url,''), c.linkedin_url),
    location = COALESCE(NULLIF(CONCAT_WS(', ', NULLIF(s.location_city,''), NULLIF(s.location_state,''), NULLIF(s.location_country,'')),''), c.location),
    domain = COALESCE(NULLIF(s.company_domain,''), c.domain),
    source = CASE WHEN c.source NOT LIKE '%%getsales%%' AND c.source IS NOT NULL AND c.source != '' THEN c.source||'+getsales' WHEN c.source IS NULL OR c.source='' THEN 'getsales' ELSE c.source END,
    getsales_raw = jsonb_build_object('pipeline_stage',s.pipeline_stage,'headline',s.headline,'active_flows',s.active_flows,'list',s.list_name,'tags',s.tags,'company_industry',s.company_industry,'company_employees_range',s.company_employees_range,'connections',s.connections_number,'followers',s.followers_number),
    updated_at = NOW()
  FROM gs_import_staging s
  WHERE c.getsales_id = s.system_uuid AND s.system_uuid IS NOT NULL AND s.system_uuid != '' AND c.deleted_at IS NULL
  RETURNING c.id
) SELECT COUNT(*) AS updated_by_getsales_id FROM ups;
""")

    print("Step 6b: Update by email...")
    psql("""
WITH ups AS (
  UPDATE contacts c SET
    getsales_id = s.system_uuid,
    first_name = COALESCE(NULLIF(s.first_name,''), c.first_name),
    last_name = COALESCE(NULLIF(s.last_name,''), c.last_name),
    company_name = COALESCE(NULLIF(s.company_name,''), c.company_name),
    job_title = COALESCE(NULLIF(s.position,''), c.job_title),
    phone = COALESCE(NULLIF(s.work_phone,''), NULLIF(s.personal_phone,''), c.phone),
    linkedin_url = COALESCE(NULLIF(s.linkedin_url,''), c.linkedin_url),
    location = COALESCE(NULLIF(CONCAT_WS(', ', NULLIF(s.location_city,''), NULLIF(s.location_state,''), NULLIF(s.location_country,'')),''), c.location),
    domain = COALESCE(NULLIF(s.company_domain,''), c.domain),
    source = CASE WHEN c.source NOT LIKE '%%getsales%%' AND c.source IS NOT NULL AND c.source != '' THEN c.source||'+getsales' WHEN c.source IS NULL OR c.source='' THEN 'getsales' ELSE c.source END,
    getsales_raw = jsonb_build_object('pipeline_stage',s.pipeline_stage,'headline',s.headline,'active_flows',s.active_flows,'list',s.list_name,'tags',s.tags,'company_industry',s.company_industry,'company_employees_range',s.company_employees_range,'connections',s.connections_number,'followers',s.followers_number),
    updated_at = NOW()
  FROM gs_import_staging s
  WHERE LOWER(c.email) = LOWER(COALESCE(NULLIF(s.work_email,''), s.personal_email))
    AND c.getsales_id IS NULL AND c.deleted_at IS NULL
    AND COALESCE(NULLIF(s.work_email,''), s.personal_email) IS NOT NULL
    AND COALESCE(NULLIF(s.work_email,''), s.personal_email) != ''
    AND NOT EXISTS (SELECT 1 FROM contacts c2 WHERE c2.getsales_id = s.system_uuid AND c2.deleted_at IS NULL)
  RETURNING c.id
) SELECT COUNT(*) AS updated_by_email FROM ups;
""")

    print("Step 6c: Update by linkedin...")
    psql("""
WITH ups AS (
  UPDATE contacts c SET
    getsales_id = s.system_uuid,
    first_name = COALESCE(NULLIF(s.first_name,''), c.first_name),
    last_name = COALESCE(NULLIF(s.last_name,''), c.last_name),
    company_name = COALESCE(NULLIF(s.company_name,''), c.company_name),
    job_title = COALESCE(NULLIF(s.position,''), c.job_title),
    email = CASE WHEN c.email LIKE '%%@linkedin.placeholder' AND NULLIF(s.work_email,'') IS NOT NULL THEN LOWER(s.work_email) ELSE c.email END,
    phone = COALESCE(NULLIF(s.work_phone,''), NULLIF(s.personal_phone,''), c.phone),
    location = COALESCE(NULLIF(CONCAT_WS(', ', NULLIF(s.location_city,''), NULLIF(s.location_state,''), NULLIF(s.location_country,'')),''), c.location),
    domain = COALESCE(NULLIF(s.company_domain,''), c.domain),
    source = CASE WHEN c.source NOT LIKE '%%getsales%%' AND c.source IS NOT NULL AND c.source != '' THEN c.source||'+getsales' WHEN c.source IS NULL OR c.source='' THEN 'getsales' ELSE c.source END,
    getsales_raw = jsonb_build_object('pipeline_stage',s.pipeline_stage,'headline',s.headline,'active_flows',s.active_flows,'list',s.list_name,'tags',s.tags,'company_industry',s.company_industry,'company_employees_range',s.company_employees_range,'connections',s.connections_number,'followers',s.followers_number),
    updated_at = NOW()
  FROM gs_import_staging s
  WHERE c.linkedin_url = s.linkedin_url AND c.getsales_id IS NULL AND c.deleted_at IS NULL
    AND s.linkedin_url IS NOT NULL AND s.linkedin_url != ''
    AND NOT EXISTS (SELECT 1 FROM contacts c2 WHERE c2.getsales_id = s.system_uuid AND c2.deleted_at IS NULL)
  RETURNING c.id
) SELECT COUNT(*) AS updated_by_linkedin FROM ups;
""")

    print("Step 6d: Insert new contacts...")
    psql("""
WITH ins AS (
  INSERT INTO contacts (
    company_id, email, first_name, last_name, company_name, job_title,
    phone, linkedin_url, location, domain, source, getsales_id,
    status, is_active, getsales_raw, created_at, updated_at
  )
  SELECT 1,
    COALESCE(LOWER(NULLIF(s.work_email,'')), LOWER(NULLIF(s.personal_email,'')), 'gs_'||s.system_uuid||'@linkedin.placeholder'),
    NULLIF(s.first_name,''), NULLIF(s.last_name,''), NULLIF(s.company_name,''), NULLIF(s.position,''),
    COALESCE(NULLIF(s.work_phone,''), NULLIF(s.personal_phone,'')),
    NULLIF(s.linkedin_url,''),
    NULLIF(CONCAT_WS(', ', NULLIF(s.location_city,''), NULLIF(s.location_state,''), NULLIF(s.location_country,'')),''),
    NULLIF(s.company_domain,''),
    'getsales', s.system_uuid, 'lead', true,
    jsonb_build_object('pipeline_stage',s.pipeline_stage,'headline',s.headline,'active_flows',s.active_flows,'list',s.list_name,'tags',s.tags,'company_industry',s.company_industry,'company_employees_range',s.company_employees_range,'connections',s.connections_number,'followers',s.followers_number),
    COALESCE(s.created_at::timestamp, NOW()), NOW()
  FROM gs_import_staging s
  WHERE s.system_uuid IS NOT NULL AND s.system_uuid != ''
    AND NOT EXISTS (SELECT 1 FROM contacts c WHERE c.getsales_id = s.system_uuid AND c.deleted_at IS NULL)
    AND NOT EXISTS (
      SELECT 1 FROM contacts c WHERE LOWER(c.email) = LOWER(COALESCE(NULLIF(s.work_email,''), s.personal_email))
        AND c.deleted_at IS NULL AND COALESCE(NULLIF(s.work_email,''), s.personal_email) IS NOT NULL
        AND COALESCE(NULLIF(s.work_email,''), s.personal_email) != '')
    AND NOT EXISTS (
      SELECT 1 FROM contacts c WHERE c.linkedin_url = s.linkedin_url AND c.deleted_at IS NULL
        AND s.linkedin_url IS NOT NULL AND s.linkedin_url != '')
  ON CONFLICT (lower(email)) WHERE deleted_at IS NULL AND email IS NOT NULL AND email != '' DO NOTHING
  RETURNING id
) SELECT COUNT(*) AS inserted FROM ins;
""")

    # Final counts
    print("\nFinal counts:")
    psql("SELECT COUNT(*) AS total_contacts FROM contacts WHERE deleted_at IS NULL;")
    psql("SELECT COUNT(*) AS getsales_contacts FROM contacts WHERE getsales_id IS NOT NULL AND deleted_at IS NULL;")
    psql("SELECT source, COUNT(*) FROM contacts WHERE deleted_at IS NULL GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10;")

    # Cleanup
    print("Cleanup...")
    psql("DROP TABLE IF EXISTS gs_import_staging;")
    subprocess.run(['docker', 'exec', 'leadgen-postgres', 'rm', '-f', '/tmp/getsales_clean.csv'])
    if os.path.exists(CLEAN_CSV):
        os.remove(CLEAN_CSV)

    print("\n=== Done ===")

if __name__ == '__main__':
    main()
