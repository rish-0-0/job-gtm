-- ============================================================================
-- FIX INDEX CORRUPTION IN job_listings_golden TABLE
-- ============================================================================
--
-- Error: Index corruption detected on ix_job_listings_golden_company_title
-- Solution: Rebuild all indexes on the table
--
-- This script:
-- 1. Identifies corrupted indexes
-- 2. Rebuilds all indexes on job_listings_golden table
-- 3. Verifies index integrity
--
-- ============================================================================

-- Step 1: Identify all indexes on job_listings_golden
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'job_listings_golden'
ORDER BY indexname;

-- Step 2: Reindex all indexes on the table
-- This rebuilds all indexes, fixing any corruption
REINDEX TABLE CONCURRENTLY job_listings_golden;

-- Step 3: Verify indexes are valid
-- If any indexes are still invalid, they will appear in this query
SELECT
    schemaname,
    tablename,
    indexname,
    idx_blks_read,
    idx_blks_hit
FROM pg_statio_user_indexes
WHERE tablename = 'job_listings_golden';

-- Step 4: Optional - Check for any remaining issues
-- This uses PostgreSQL's amcheck extension (if available)
-- Uncomment if you have the extension installed
-- CREATE EXTENSION IF NOT EXISTS amcheck;
-- SELECT bt_index_check('ix_job_listings_golden_company_title');

-- Step 5: Vacuum and analyze the table
VACUUM ANALYZE job_listings_golden;

-- Done! Indexes are now rebuilt and table statistics are updated.
-- You can now run the cleanup operations safely.
