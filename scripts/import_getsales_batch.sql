-- Add row numbers to staging for batching
ALTER TABLE gs_import_staging ADD COLUMN IF NOT EXISTS row_id SERIAL;

-- Create index on staging
CREATE INDEX IF NOT EXISTS idx_staging_rowid ON gs_import_staging(row_id);
CREATE INDEX IF NOT EXISTS idx_staging_uuid ON gs_import_staging(system_uuid);

-- Batch 1: rows 1-10000
DO $$
DECLARE
  batch_start INT := 1;
  batch_size INT := 10000;
  batch_num INT := 0;
  total_inserted INT := 0;
  total_updated INT := 0;
  batch_inserted INT;
  batch_updated INT;
BEGIN
  LOOP
    batch_num := batch_num + 1;

    WITH ins AS (
      INSERT INTO contacts (
        company_id, email, first_name, last_name, company_name, job_title,
        phone, linkedin_url, location, domain, source, getsales_id,
        status, is_active, getsales_raw, created_at, updated_at
      )
      SELECT
        1,
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
      WHERE s.row_id >= batch_start AND s.row_id < batch_start + batch_size
        AND s.system_uuid IS NOT NULL AND s.system_uuid != ''
      ON CONFLICT (lower(email)) WHERE deleted_at IS NULL AND email IS NOT NULL AND email != ''
      DO UPDATE SET
        getsales_id = COALESCE(contacts.getsales_id, EXCLUDED.getsales_id),
        first_name = COALESCE(NULLIF(EXCLUDED.first_name,''), contacts.first_name),
        last_name = COALESCE(NULLIF(EXCLUDED.last_name,''), contacts.last_name),
        company_name = COALESCE(NULLIF(EXCLUDED.company_name,''), contacts.company_name),
        job_title = COALESCE(NULLIF(EXCLUDED.job_title,''), contacts.job_title),
        phone = COALESCE(NULLIF(EXCLUDED.phone,''), contacts.phone),
        linkedin_url = COALESCE(NULLIF(EXCLUDED.linkedin_url,''), contacts.linkedin_url),
        location = COALESCE(NULLIF(EXCLUDED.location,''), contacts.location),
        domain = COALESCE(NULLIF(EXCLUDED.domain,''), contacts.domain),
        source = CASE WHEN contacts.source NOT LIKE '%getsales%' AND contacts.source IS NOT NULL AND contacts.source != '' THEN contacts.source||'+getsales' WHEN contacts.source IS NULL OR contacts.source='' THEN 'getsales' ELSE contacts.source END,
        getsales_raw = EXCLUDED.getsales_raw,
        updated_at = NOW()
      RETURNING id, (xmax = 0) AS was_insert
    )
    SELECT
      COUNT(*) FILTER (WHERE was_insert),
      COUNT(*) FILTER (WHERE NOT was_insert)
    INTO batch_inserted, batch_updated
    FROM ins;

    total_inserted := total_inserted + COALESCE(batch_inserted, 0);
    total_updated := total_updated + COALESCE(batch_updated, 0);

    RAISE NOTICE 'Batch %: start=%, inserted=%, updated=%', batch_num, batch_start, batch_inserted, batch_updated;

    batch_start := batch_start + batch_size;
    EXIT WHEN batch_start > 130000;
  END LOOP;

  RAISE NOTICE 'TOTAL: inserted=%, updated=%', total_inserted, total_updated;
END $$;

-- Final stats
SELECT COUNT(*) AS total_contacts FROM contacts WHERE deleted_at IS NULL;
SELECT COUNT(*) AS getsales_contacts FROM contacts WHERE getsales_id IS NOT NULL AND deleted_at IS NULL;
SELECT source, COUNT(*) FROM contacts WHERE deleted_at IS NULL GROUP BY source ORDER BY COUNT(*) DESC LIMIT 15;
