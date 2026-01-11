-- ============================================================================
-- GOLDEN JOB LISTINGS DATA CLEANUP SCRIPT
-- ============================================================================
-- This script can be run directly to cleanup data without using migrations
-- Usage: psql postgresql://user:pass@host:5432/db -f cleanup_golden_job_listings.sql
--
-- Operations:
-- 1. Standardize NULL values (None, NONE, none, NULL, null, N/A, n/a)
-- 2. Fix pipe-separated values (a|b|c -> a)
-- 3. Trim excess whitespace from all fields
-- ============================================================================

-- Start transaction for atomicity
BEGIN;

-- ============================================================================
-- STEP 1: STANDARDIZE NULL VALUES
-- ============================================================================

-- Clean location_city
UPDATE job_listings_golden
SET location_city = NULL
WHERE location_city IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean location_state
UPDATE job_listings_golden
SET location_state = NULL
WHERE location_state IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean location_country
UPDATE job_listings_golden
SET location_country = NULL
WHERE location_country IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean job_location_normalized
UPDATE job_listings_golden
SET job_location_normalized = NULL
WHERE job_location_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean seniority_level_normalized
UPDATE job_listings_golden
SET seniority_level_normalized = NULL
WHERE seniority_level_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean work_arrangement_normalized
UPDATE job_listings_golden
SET work_arrangement_normalized = NULL
WHERE work_arrangement_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean company_industry
UPDATE job_listings_golden
SET company_industry = NULL
WHERE company_industry IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean company_size
UPDATE job_listings_golden
SET company_size = NULL
WHERE company_size IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean primary_role
UPDATE job_listings_golden
SET primary_role = NULL
WHERE primary_role IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean role_category
UPDATE job_listings_golden
SET role_category = NULL
WHERE role_category IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean employment_type_normalized
UPDATE job_listings_golden
SET employment_type_normalized = NULL
WHERE employment_type_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean job_role
UPDATE job_listings_golden
SET job_role = NULL
WHERE job_role IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- Clean company_title
UPDATE job_listings_golden
SET company_title = NULL
WHERE company_title IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
AND enrichment_status = 'completed';

-- ============================================================================
-- STEP 2: FIX PIPE-SEPARATED VALUES (a|b|c -> a)
-- ============================================================================

-- location_city
UPDATE job_listings_golden
SET location_city = TRIM(SPLIT_PART(location_city, '|', 1))
WHERE location_city LIKE '%|%'
AND location_city IS NOT NULL
AND location_city NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- location_state
UPDATE job_listings_golden
SET location_state = TRIM(SPLIT_PART(location_state, '|', 1))
WHERE location_state LIKE '%|%'
AND location_state IS NOT NULL
AND location_state NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- location_country
UPDATE job_listings_golden
SET location_country = TRIM(SPLIT_PART(location_country, '|', 1))
WHERE location_country LIKE '%|%'
AND location_country IS NOT NULL
AND location_country NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- job_location_normalized
UPDATE job_listings_golden
SET job_location_normalized = TRIM(SPLIT_PART(job_location_normalized, '|', 1))
WHERE job_location_normalized LIKE '%|%'
AND job_location_normalized IS NOT NULL
AND job_location_normalized NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- seniority_level_normalized
UPDATE job_listings_golden
SET seniority_level_normalized = TRIM(SPLIT_PART(seniority_level_normalized, '|', 1))
WHERE seniority_level_normalized LIKE '%|%'
AND seniority_level_normalized IS NOT NULL
AND seniority_level_normalized NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- work_arrangement_normalized
UPDATE job_listings_golden
SET work_arrangement_normalized = TRIM(SPLIT_PART(work_arrangement_normalized, '|', 1))
WHERE work_arrangement_normalized LIKE '%|%'
AND work_arrangement_normalized IS NOT NULL
AND work_arrangement_normalized NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- company_industry
UPDATE job_listings_golden
SET company_industry = TRIM(SPLIT_PART(company_industry, '|', 1))
WHERE company_industry LIKE '%|%'
AND company_industry IS NOT NULL
AND company_industry NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- company_size
UPDATE job_listings_golden
SET company_size = TRIM(SPLIT_PART(company_size, '|', 1))
WHERE company_size LIKE '%|%'
AND company_size IS NOT NULL
AND company_size NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- primary_role
UPDATE job_listings_golden
SET primary_role = TRIM(SPLIT_PART(primary_role, '|', 1))
WHERE primary_role LIKE '%|%'
AND primary_role IS NOT NULL
AND primary_role NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- role_category
UPDATE job_listings_golden
SET role_category = TRIM(SPLIT_PART(role_category, '|', 1))
WHERE role_category LIKE '%|%'
AND role_category IS NOT NULL
AND role_category NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- employment_type_normalized
UPDATE job_listings_golden
SET employment_type_normalized = TRIM(SPLIT_PART(employment_type_normalized, '|', 1))
WHERE employment_type_normalized LIKE '%|%'
AND employment_type_normalized IS NOT NULL
AND employment_type_normalized NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- job_role
UPDATE job_listings_golden
SET job_role = TRIM(SPLIT_PART(job_role, '|', 1))
WHERE job_role LIKE '%|%'
AND job_role IS NOT NULL
AND job_role NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- company_title
UPDATE job_listings_golden
SET company_title = TRIM(SPLIT_PART(company_title, '|', 1))
WHERE company_title LIKE '%|%'
AND company_title IS NOT NULL
AND company_title NOT IN ('', 'None', 'NULL')
AND enrichment_status = 'completed';

-- ============================================================================
-- STEP 3: TRIM EXCESS WHITESPACE
-- ============================================================================

UPDATE job_listings_golden
SET
    location_city = NULLIF(TRIM(location_city), ''),
    location_state = NULLIF(TRIM(location_state), ''),
    location_country = NULLIF(TRIM(location_country), ''),
    job_location_normalized = NULLIF(TRIM(job_location_normalized), ''),
    seniority_level_normalized = NULLIF(TRIM(seniority_level_normalized), ''),
    work_arrangement_normalized = NULLIF(TRIM(work_arrangement_normalized), ''),
    company_industry = NULLIF(TRIM(company_industry), ''),
    company_size = NULLIF(TRIM(company_size), ''),
    primary_role = NULLIF(TRIM(primary_role), ''),
    role_category = NULLIF(TRIM(role_category), ''),
    employment_type_normalized = NULLIF(TRIM(employment_type_normalized), ''),
    job_role = NULLIF(TRIM(job_role), ''),
    company_title = NULLIF(TRIM(company_title), ''),
    updated_at = NOW()
WHERE enrichment_status = 'completed';

-- ============================================================================
-- STEP 4: REFRESH MATERIALIZED VIEW
-- ============================================================================

REFRESH MATERIALIZED VIEW CONCURRENTLY mv_root_data;

-- ============================================================================
-- COMMIT TRANSACTION
-- ============================================================================

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (Run after cleanup)
-- ============================================================================

-- Check cleanup effectiveness
SELECT
    COUNT(*) as total_rows,
    SUM(CASE WHEN location_city IN ('None', 'NONE', 'none') THEN 1 ELSE 0 END) as none_cities,
    SUM(CASE WHEN location_city LIKE '%|%' THEN 1 ELSE 0 END) as pipe_cities,
    SUM(CASE WHEN primary_role IN ('None', 'NONE', 'none') THEN 1 ELSE 0 END) as none_roles,
    SUM(CASE WHEN primary_role LIKE '%|%' THEN 1 ELSE 0 END) as pipe_roles
FROM job_listings_golden
WHERE enrichment_status = 'completed';

-- Expected after cleanup: All values should be 0
-- If you see values > 0, something went wrong
