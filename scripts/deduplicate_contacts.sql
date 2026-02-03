-- CRM Contact Deduplication Script - Optimized Version
-- Merges duplicate contacts and keeps the most complete record

BEGIN;

-- Before stats
SELECT 'Before deduplication:' AS status;
SELECT COUNT(*) AS total_contacts FROM contacts;
SELECT COUNT(*) FILTER (WHERE smartlead_id IS NOT NULL AND getsales_id IS NOT NULL) AS merged_both_ids FROM contacts;

-- Step 1: Aggregate all IDs by email
CREATE TEMP TABLE email_ids AS
SELECT 
    LOWER(email) as email_lower,
    MAX(smartlead_id) as merged_smartlead_id,
    MAX(getsales_id) as merged_getsales_id,
    COUNT(*) as dup_count
FROM contacts
WHERE email IS NOT NULL AND email != ''
GROUP BY LOWER(email);

SELECT 'Unique emails:' AS status;
SELECT COUNT(*) AS unique_emails FROM email_ids;
SELECT 'Emails with duplicates:' AS status;
SELECT COUNT(*) FILTER (WHERE dup_count > 1) AS emails_with_dups FROM email_ids;

-- Step 2: Find the best record to keep for each email
CREATE TEMP TABLE best_records AS
SELECT DISTINCT ON (LOWER(email))
    id,
    email
FROM contacts
WHERE email IS NOT NULL AND email != ''
ORDER BY 
    LOWER(email),
    CASE WHEN smartlead_id IS NOT NULL AND getsales_id IS NOT NULL THEN 0 
         WHEN smartlead_id IS NOT NULL OR getsales_id IS NOT NULL THEN 1 
         ELSE 2 END,
    updated_at DESC;

SELECT 'Best records selected:' AS status;
SELECT COUNT(*) AS best_records FROM best_records;

-- Step 3: Update best records with merged IDs
UPDATE contacts c
SET 
    smartlead_id = COALESCE(c.smartlead_id, e.merged_smartlead_id),
    getsales_id = COALESCE(c.getsales_id, e.merged_getsales_id),
    updated_at = NOW()
FROM best_records b
JOIN email_ids e ON LOWER(b.email) = e.email_lower
WHERE c.id = b.id
  AND (c.smartlead_id IS NULL AND e.merged_smartlead_id IS NOT NULL
       OR c.getsales_id IS NULL AND e.merged_getsales_id IS NOT NULL);

SELECT 'Records updated with merged IDs:' AS status;

-- Step 4: Delete duplicates (records not in best_records)
DELETE FROM contacts
WHERE email IS NOT NULL 
  AND email != ''
  AND id NOT IN (SELECT id FROM best_records);

SELECT 'Records deleted:' AS status;

-- After stats
SELECT 'After deduplication:' AS status;
SELECT COUNT(*) AS total_contacts FROM contacts;
SELECT COUNT(*) FILTER (WHERE smartlead_id IS NOT NULL AND getsales_id IS NOT NULL) AS merged_both_ids FROM contacts;

SELECT 'Remaining duplicates (should be 0):' AS status;
SELECT COUNT(*) - COUNT(DISTINCT LOWER(email)) AS remaining_duplicates 
FROM contacts 
WHERE email IS NOT NULL AND email != '';

COMMIT;
