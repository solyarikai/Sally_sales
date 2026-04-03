-- Add segment/geo/language columns to search_queries for systematic query approach
ALTER TABLE search_queries ADD COLUMN IF NOT EXISTS segment VARCHAR(100);
ALTER TABLE search_queries ADD COLUMN IF NOT EXISTS geo VARCHAR(100);
ALTER TABLE search_queries ADD COLUMN IF NOT EXISTS language VARCHAR(10);

-- Add matched_segment to search_results for segment classification
ALTER TABLE search_results ADD COLUMN IF NOT EXISTS matched_segment VARCHAR(100);

-- Indexes for filtering/grouping by segment and geo
CREATE INDEX IF NOT EXISTS ix_search_queries_segment ON search_queries (segment);
CREATE INDEX IF NOT EXISTS ix_search_queries_geo ON search_queries (geo);
CREATE INDEX IF NOT EXISTS ix_search_queries_segment_geo ON search_queries (segment, geo);
CREATE INDEX IF NOT EXISTS ix_search_results_matched_segment ON search_results (matched_segment);
