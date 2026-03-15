#!/bin/bash
# Import GetSales CSV exports into contacts table via staging table + upsert
set -e

EXPORT_DIR="$(dirname "$0")/getsales_exports"
COMBINED="/tmp/getsales_combined.csv"
DOCKER_PSQL="docker exec -i leadgen-postgres psql -U leadgen -d leadgen"

echo "=== GetSales CSV Import ==="

# Step 1: Combine all CSVs, keeping only the first header
echo "Step 1: Combining CSVs..."
FIRST=1
for f in "$EXPORT_DIR"/contacts_export_*.csv; do
  if [ $FIRST -eq 1 ]; then
    cat "$f" > "$COMBINED"
    FIRST=0
  else
    tail -n +2 "$f" >> "$COMBINED"
  fi
done
TOTAL_LINES=$(wc -l < "$COMBINED")
echo "  Combined: $((TOTAL_LINES - 1)) data rows"

# Step 2: Create staging table
echo "Step 2: Creating staging table..."
$DOCKER_PSQL <<'SQL'
DROP TABLE IF EXISTS gs_import_staging;
CREATE TABLE gs_import_staging (
  system_uuid TEXT,
  pipeline_stage TEXT,
  full_name TEXT,
  first_name TEXT,
  last_name TEXT,
  position TEXT,
  headline TEXT,
  about TEXT,
  linkedin_id TEXT,
  sales_navigator_id TEXT,
  linkedin_nickname TEXT,
  linkedin_url TEXT,
  facebook_nickname TEXT,
  twitter_nickname TEXT,
  work_email TEXT,
  personal_email TEXT,
  work_phone TEXT,
  personal_phone TEXT,
  connections_number TEXT,
  followers_number TEXT,
  primary_language TEXT,
  has_open_profile TEXT,
  has_verified_profile TEXT,
  has_premium TEXT,
  location_country TEXT,
  location_state TEXT,
  location_city TEXT,
  active_flows TEXT,
  list_name TEXT,
  tags TEXT,
  company_name TEXT,
  company_industry TEXT,
  company_linkedin_id TEXT,
  company_domain TEXT,
  company_linkedin_url TEXT,
  company_employees_range TEXT,
  company_headquarter TEXT,
  cf_location TEXT,
  cf_competitor_client TEXT,
  cf_message1 TEXT,
  cf_message2 TEXT,
  cf_message3 TEXT,
  cf_personalization TEXT,
  cf_compersonalization TEXT,
  cf_personalization1 TEXT,
  cf_message4 TEXT,
  cf_linkedin_personalization TEXT,
  cf_subject TEXT,
  created_at TEXT
);
SQL

# Step 3: COPY data into staging
echo "Step 3: Loading CSV data into staging table..."
docker cp "$COMBINED" leadgen-postgres:/tmp/getsales_combined.csv
$DOCKER_PSQL <<'SQL'
\copy gs_import_staging FROM '/tmp/getsales_combined.csv' WITH (FORMAT csv, HEADER true, QUOTE '"', ESCAPE '"');
SQL

STAGING_COUNT=$($DOCKER_PSQL -t -c "SELECT COUNT(*) FROM gs_import_staging;")
echo "  Loaded: $(echo $STAGING_COUNT | xargs) rows into staging"

# Step 4: Deduplicate staging (keep first occurrence per system_uuid)
echo "Step 4: Deduplicating staging..."
$DOCKER_PSQL <<'SQL'
DELETE FROM gs_import_staging a
USING gs_import_staging b
WHERE a.ctid > b.ctid
  AND a.system_uuid = b.system_uuid
  AND a.system_uuid IS NOT NULL
  AND a.system_uuid != '';
SQL

DEDUP_COUNT=$($DOCKER_PSQL -t -c "SELECT COUNT(*) FROM gs_import_staging;")
echo "  After dedup: $(echo $DEDUP_COUNT | xargs) unique rows"

# Step 5: Upsert into contacts
echo "Step 5: Upserting into contacts table..."
$DOCKER_PSQL <<'SQL'
-- First: UPDATE existing contacts that match by getsales_id
WITH updates AS (
  UPDATE contacts c
  SET
    first_name = COALESCE(NULLIF(s.first_name, ''), c.first_name),
    last_name = COALESCE(NULLIF(s.last_name, ''), c.last_name),
    company_name = COALESCE(NULLIF(s.company_name, ''), c.company_name),
    job_title = COALESCE(NULLIF(s.position, ''), c.job_title),
    phone = COALESCE(NULLIF(s.work_phone, ''), NULLIF(s.personal_phone, ''), c.phone),
    linkedin_url = COALESCE(NULLIF(s.linkedin_url, ''), c.linkedin_url),
    location = COALESCE(
      NULLIF(CONCAT_WS(', ',
        NULLIF(s.location_city, ''),
        NULLIF(s.location_state, ''),
        NULLIF(s.location_country, '')
      ), ''),
      c.location
    ),
    domain = COALESCE(NULLIF(s.company_domain, ''), c.domain),
    source = CASE
      WHEN c.source NOT LIKE '%getsales%' AND c.source IS NOT NULL AND c.source != ''
      THEN c.source || '+getsales'
      WHEN c.source IS NULL OR c.source = '' THEN 'getsales'
      ELSE c.source
    END,
    getsales_raw = jsonb_build_object(
      'pipeline_stage', s.pipeline_stage,
      'headline', s.headline,
      'active_flows', s.active_flows,
      'list', s.list_name,
      'tags', s.tags,
      'company_industry', s.company_industry,
      'company_employees_range', s.company_employees_range,
      'connections', s.connections_number,
      'followers', s.followers_number
    ),
    updated_at = NOW()
  FROM gs_import_staging s
  WHERE c.getsales_id = s.system_uuid
    AND s.system_uuid IS NOT NULL AND s.system_uuid != ''
    AND c.deleted_at IS NULL
  RETURNING c.id, s.system_uuid
)
SELECT COUNT(*) AS updated_by_getsales_id FROM updates;

-- Second: UPDATE existing contacts that match by email (no getsales_id match)
WITH email_updates AS (
  UPDATE contacts c
  SET
    getsales_id = s.system_uuid,
    first_name = COALESCE(NULLIF(s.first_name, ''), c.first_name),
    last_name = COALESCE(NULLIF(s.last_name, ''), c.last_name),
    company_name = COALESCE(NULLIF(s.company_name, ''), c.company_name),
    job_title = COALESCE(NULLIF(s.position, ''), c.job_title),
    phone = COALESCE(NULLIF(s.work_phone, ''), NULLIF(s.personal_phone, ''), c.phone),
    linkedin_url = COALESCE(NULLIF(s.linkedin_url, ''), c.linkedin_url),
    location = COALESCE(
      NULLIF(CONCAT_WS(', ',
        NULLIF(s.location_city, ''),
        NULLIF(s.location_state, ''),
        NULLIF(s.location_country, '')
      ), ''),
      c.location
    ),
    domain = COALESCE(NULLIF(s.company_domain, ''), c.domain),
    source = CASE
      WHEN c.source NOT LIKE '%getsales%' AND c.source IS NOT NULL AND c.source != ''
      THEN c.source || '+getsales'
      WHEN c.source IS NULL OR c.source = '' THEN 'getsales'
      ELSE c.source
    END,
    getsales_raw = jsonb_build_object(
      'pipeline_stage', s.pipeline_stage,
      'headline', s.headline,
      'active_flows', s.active_flows,
      'list', s.list_name,
      'tags', s.tags,
      'company_industry', s.company_industry,
      'company_employees_range', s.company_employees_range,
      'connections', s.connections_number,
      'followers', s.followers_number
    ),
    updated_at = NOW()
  FROM gs_import_staging s
  WHERE LOWER(c.email) = LOWER(COALESCE(NULLIF(s.work_email, ''), s.personal_email))
    AND c.getsales_id IS NULL
    AND c.deleted_at IS NULL
    AND COALESCE(NULLIF(s.work_email, ''), s.personal_email) IS NOT NULL
    AND COALESCE(NULLIF(s.work_email, ''), s.personal_email) != ''
    -- Skip rows already matched by getsales_id
    AND NOT EXISTS (
      SELECT 1 FROM contacts c2
      WHERE c2.getsales_id = s.system_uuid AND c2.deleted_at IS NULL
    )
  RETURNING c.id, s.system_uuid
)
SELECT COUNT(*) AS updated_by_email FROM email_updates;

-- Third: UPDATE existing contacts that match by linkedin_url
WITH linkedin_updates AS (
  UPDATE contacts c
  SET
    getsales_id = s.system_uuid,
    first_name = COALESCE(NULLIF(s.first_name, ''), c.first_name),
    last_name = COALESCE(NULLIF(s.last_name, ''), c.last_name),
    company_name = COALESCE(NULLIF(s.company_name, ''), c.company_name),
    job_title = COALESCE(NULLIF(s.position, ''), c.job_title),
    email = CASE
      WHEN c.email LIKE '%@linkedin.placeholder' AND NULLIF(s.work_email, '') IS NOT NULL
      THEN LOWER(s.work_email)
      ELSE c.email
    END,
    phone = COALESCE(NULLIF(s.work_phone, ''), NULLIF(s.personal_phone, ''), c.phone),
    location = COALESCE(
      NULLIF(CONCAT_WS(', ',
        NULLIF(s.location_city, ''),
        NULLIF(s.location_state, ''),
        NULLIF(s.location_country, '')
      ), ''),
      c.location
    ),
    domain = COALESCE(NULLIF(s.company_domain, ''), c.domain),
    source = CASE
      WHEN c.source NOT LIKE '%getsales%' AND c.source IS NOT NULL AND c.source != ''
      THEN c.source || '+getsales'
      WHEN c.source IS NULL OR c.source = '' THEN 'getsales'
      ELSE c.source
    END,
    getsales_raw = jsonb_build_object(
      'pipeline_stage', s.pipeline_stage,
      'headline', s.headline,
      'active_flows', s.active_flows,
      'list', s.list_name,
      'tags', s.tags,
      'company_industry', s.company_industry,
      'company_employees_range', s.company_employees_range,
      'connections', s.connections_number,
      'followers', s.followers_number
    ),
    updated_at = NOW()
  FROM gs_import_staging s
  WHERE c.linkedin_url = s.linkedin_url
    AND c.getsales_id IS NULL
    AND c.deleted_at IS NULL
    AND s.linkedin_url IS NOT NULL AND s.linkedin_url != ''
    -- Skip already matched
    AND NOT EXISTS (
      SELECT 1 FROM contacts c2
      WHERE c2.getsales_id = s.system_uuid AND c2.deleted_at IS NULL
    )
  RETURNING c.id, s.system_uuid
)
SELECT COUNT(*) AS updated_by_linkedin FROM linkedin_updates;

-- Fourth: INSERT new contacts (not matched by getsales_id, email, or linkedin)
WITH new_contacts AS (
  INSERT INTO contacts (
    company_id, email, first_name, last_name, company_name, job_title,
    phone, linkedin_url, location, domain, source, getsales_id,
    status, is_active, getsales_raw, created_at, updated_at
  )
  SELECT
    1, -- company_id
    COALESCE(
      LOWER(NULLIF(s.work_email, '')),
      LOWER(NULLIF(s.personal_email, '')),
      'gs_' || s.system_uuid || '@linkedin.placeholder'
    ),
    NULLIF(s.first_name, ''),
    NULLIF(s.last_name, ''),
    NULLIF(s.company_name, ''),
    NULLIF(s.position, ''),
    COALESCE(NULLIF(s.work_phone, ''), NULLIF(s.personal_phone, '')),
    NULLIF(s.linkedin_url, ''),
    NULLIF(CONCAT_WS(', ',
      NULLIF(s.location_city, ''),
      NULLIF(s.location_state, ''),
      NULLIF(s.location_country, '')
    ), ''),
    NULLIF(s.company_domain, ''),
    'getsales',
    s.system_uuid,
    'lead',
    true,
    jsonb_build_object(
      'pipeline_stage', s.pipeline_stage,
      'headline', s.headline,
      'active_flows', s.active_flows,
      'list', s.list_name,
      'tags', s.tags,
      'company_industry', s.company_industry,
      'company_employees_range', s.company_employees_range,
      'connections', s.connections_number,
      'followers', s.followers_number
    ),
    COALESCE(s.created_at::timestamp, NOW()),
    NOW()
  FROM gs_import_staging s
  WHERE s.system_uuid IS NOT NULL AND s.system_uuid != ''
    -- Not already in contacts by getsales_id
    AND NOT EXISTS (
      SELECT 1 FROM contacts c WHERE c.getsales_id = s.system_uuid AND c.deleted_at IS NULL
    )
    -- Not already in contacts by email
    AND NOT EXISTS (
      SELECT 1 FROM contacts c
      WHERE LOWER(c.email) = LOWER(COALESCE(NULLIF(s.work_email, ''), s.personal_email))
        AND c.deleted_at IS NULL
        AND COALESCE(NULLIF(s.work_email, ''), s.personal_email) IS NOT NULL
        AND COALESCE(NULLIF(s.work_email, ''), s.personal_email) != ''
    )
    -- Not already in contacts by linkedin
    AND NOT EXISTS (
      SELECT 1 FROM contacts c
      WHERE c.linkedin_url = s.linkedin_url
        AND c.deleted_at IS NULL
        AND s.linkedin_url IS NOT NULL AND s.linkedin_url != ''
    )
  ON CONFLICT (lower(email)) WHERE deleted_at IS NULL AND email IS NOT NULL AND email != ''
  DO NOTHING
  RETURNING id
)
SELECT COUNT(*) AS inserted FROM new_contacts;
SQL

# Step 6: Final count
echo ""
echo "Step 6: Final counts..."
$DOCKER_PSQL -c "SELECT COUNT(*) AS total_contacts FROM contacts WHERE deleted_at IS NULL;"
$DOCKER_PSQL -c "SELECT COUNT(*) AS getsales_contacts FROM contacts WHERE getsales_id IS NOT NULL AND deleted_at IS NULL;"
$DOCKER_PSQL -c "SELECT source, COUNT(*) FROM contacts WHERE deleted_at IS NULL GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10;"

# Step 7: Cleanup
echo "Step 7: Cleanup..."
$DOCKER_PSQL -c "DROP TABLE IF EXISTS gs_import_staging;"
docker exec leadgen-postgres rm -f /tmp/getsales_combined.csv
rm -f "$COMBINED"

echo ""
echo "=== Import complete ==="
