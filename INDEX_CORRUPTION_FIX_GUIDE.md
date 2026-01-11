# Index Corruption Fix Guide

## Problem

When running the data cleanup operation, you encounter this error:

```
psycopg2.errors.IndexCorrupted: table tid from new index tuple (1753,7) cannot find insert offset between offsets 13 and 16 of block 20 in index "ix_job_listings_golden_company_title"
```

## What This Means

PostgreSQL has detected corruption in one or more indexes on the `job_listings_golden` table. This typically happens due to:

1. **Server crash or unexpected shutdown** - Indexes may not have been properly synchronized with the table
2. **Hardware issues** - Disk errors during index operations
3. **Long-running transactions** - That interfered with index operations
4. **Concurrent index creation** - That failed or was interrupted
5. **Bug in PostgreSQL** (rare) - Index management issues

## Impact

- Data cleanup cannot proceed
- Queries using those indexes may fail
- New inserts/updates may fail
- The table itself is usually intact, just the indexes are corrupt

## Solutions

### Solution 1: Quick Fix Using SQL (Recommended)

This is the fastest way to fix the corruption.

```bash
# Connect to PostgreSQL
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm

# Run the fix script
\i /path/to/fix_index_corruption.sql
```

Or run the SQL directly:

```sql
-- This rebuilds all indexes on the table
REINDEX TABLE CONCURRENTLY job_listings_golden;

-- Update table statistics
VACUUM ANALYZE job_listings_golden;
```

**Time:** 2-10 minutes (depending on data size)

### Solution 2: Python Script (Programmatic)

```bash
cd workflow-svc

# Run the Python script
python fix_index_corruption.py
```

The script:
- Lists all current indexes
- Rebuilds them using CONCURRENTLY (non-blocking)
- Verifies integrity after rebuild
- Updates table statistics
- Provides detailed logging

**Time:** 2-10 minutes

### Solution 3: Docker/Container Environment

If running in Docker:

```bash
# Find the container name
docker ps | grep postgres

# Connect to the database
docker exec -it <postgres_container> psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm

# Run the fix
\i /path/to/fix_index_corruption.sql
```

## Step-by-Step Fix

### 1. Before Starting

Take a backup (optional but recommended):
```bash
pg_dump postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm \
  --table=job_listings_golden \
  -Fc > job_listings_golden_backup.dump
```

### 2. Run the Reindex

**Option A: Using SQL file**
```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm \
  -f /path/to/fix_index_corruption.sql
```

**Option B: Using Python script**
```bash
cd workflow-svc
python fix_index_corruption.py
```

**Option C: Direct SQL commands**
```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm -c \
  "REINDEX TABLE CONCURRENTLY job_listings_golden;"

psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm -c \
  "VACUUM ANALYZE job_listings_golden;"
```

### 3. Verify the Fix

Check that the table is now accessible:

```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm -c \
  "SELECT COUNT(*) FROM job_listings_golden WHERE enrichment_status = 'completed';"
```

Should return a row count without errors.

### 4. Run Data Cleanup

Once indexes are fixed, run the cleanup:

```bash
# Via API
curl -X POST http://localhost:8001/api/data-cleanup/cleanup-and-refresh \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "include_whitespace_trim": true,
    "include_pipe_separation": true,
    "include_null_standardization": true
  }'
```

Or via the UI: Navigate to `http://localhost:5173/cleanup` and click "Run Cleanup"

## What Gets Fixed

Running `REINDEX TABLE CONCURRENTLY` will:

✅ **Rebuild all indexes** on the table:
- `ix_job_listings_golden_source_job_id`
- `ix_job_listings_golden_company_title`
- `ix_job_listings_golden_scraper_source`
- `ix_job_listings_golden_enrichment_status`
- `ix_job_listings_golden_detail_scrape_status`
- `ix_job_listings_golden_seniority_level_normalized`
- `ix_job_listings_golden_posting_url` (unique)

✅ **Fix corruption** in the B-tree index structures
✅ **Maintain concurrent access** (CONCURRENTLY flag)
✅ **Preserve all data** (only indexes are rebuilt)

## Performance Impact

### During Reindex
- **Duration:** 2-10 minutes (depending on data size)
- **Disk I/O:** High (reading and rewriting indexes)
- **Memory:** Moderate increase
- **Locks:** Minimal (with CONCURRENTLY flag)
- **Table Access:** Still readable, writes may be slower

### After Reindex
- **Query Performance:** Back to normal or improved
- **Cleanup Operations:** Can proceed normally
- **Space Usage:** May be slightly reduced

## Preventing Future Corruption

### 1. Regular Maintenance

Add to a cron job (weekly):
```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm -c \
  "VACUUM ANALYZE job_listings_golden;"
```

### 2. Monitor Index Health

Create a monitoring script that checks for issues:
```sql
-- Check for bloated indexes
SELECT
    schemaname,
    tablename,
    indexname,
    idx_blks_read,
    idx_blks_hit,
    CASE
        WHEN idx_blks_hit = 0 THEN 'Not used'
        WHEN idx_blks_hit > 0 THEN 'In use'
    END as status
FROM pg_statio_user_indexes
WHERE tablename = 'job_listings_golden'
ORDER BY idx_blks_read DESC;
```

### 3. Monitor for Corruption

If you have the `amcheck` extension:

```sql
-- Create the extension (once)
CREATE EXTENSION IF NOT EXISTS amcheck;

-- Check for corruption (run periodically)
SELECT bt_index_check('ix_job_listings_golden_company_title');

-- If all indexes are healthy, this returns nothing
```

### 4. Prevent Crashes

- Keep PostgreSQL updated
- Monitor disk space
- Ensure database server has adequate memory
- Use proper shutdown procedures (never force-kill the process)
- Monitor transaction logs

## Troubleshooting

### Issue: REINDEX Fails with Permission Error

```
ERROR: permission denied for schema public
```

**Solution:** Run with a superuser or the database owner:
```bash
psql -U postgres postgresql://...

# Or if using the same user:
# Make sure the user has ALTER privilege on the table
```

### Issue: REINDEX Takes Too Long

```
-- Monitor progress (in another terminal)
SELECT query, pid, usename FROM pg_stat_activity
WHERE query LIKE '%REINDEX%';
```

**Solution:** This is normal for large tables. Wait or:
1. Reduce other workload
2. Increase maintenance_work_mem in PostgreSQL config
3. Use non-concurrent reindex (faster but locks table):
   ```sql
   REINDEX TABLE job_listings_golden;
   ```

### Issue: Still Getting Index Corruption Error

**Possible causes:**
1. Not all indexes were rebuilt
2. Issue with the data itself (not just indexes)
3. PostgreSQL bug

**Solution:**
1. Try dropping and recreating the table:
   ```bash
   # Backup first!
   pg_dump ... > backup.sql

   # Drop and recreate
   # This is drastic - only if REINDEX doesn't work
   ```

2. Check PostgreSQL logs:
   ```bash
   # Find log file location
   psql -c "SHOW log_directory;"

   # Check for hardware errors
   cat /var/log/syslog | grep -i error
   ```

### Issue: Table Still Has Corruption After Reindex

```
-- Check integrity (if amcheck is available)
SELECT bt_index_check('ix_job_listings_golden_company_title');

-- If errors persist:
-- 1. Report to PostgreSQL developers
-- 2. Consider downgrading/upgrading PostgreSQL version
-- 3. Check for hardware issues
```

## Recovery from Backup

If reindexing doesn't work and you have a backup:

```bash
# Restore from backup
pg_restore -d jobgtm job_listings_golden_backup.dump

# Verify
psql -c "SELECT COUNT(*) FROM job_listings_golden;"
```

## Reporting the Issue

If the issue persists after reindexing, check:

1. **PostgreSQL version:**
   ```bash
   psql --version
   ```

2. **Database logs:**
   ```bash
   psql -c "SHOW log_directory;"
   cat <log_directory>/postgresql-*.log | tail -100
   ```

3. **System logs:**
   ```bash
   sudo journalctl -xe | tail -100
   dmesg | tail -50
   ```

Report to PostgreSQL maintainers with these details.

## Files Provided

- `fix_index_corruption.sql` - SQL script for fixing corruption
- `fix_index_corruption.py` - Python script for fixing corruption
- This guide

## Quick Reference

| Task | Command |
|------|---------|
| **Fix indexes (concurrent)** | `REINDEX TABLE CONCURRENTLY job_listings_golden;` |
| **Fix indexes (fast)** | `REINDEX TABLE job_listings_golden;` |
| **Update statistics** | `VACUUM ANALYZE job_listings_golden;` |
| **Check index health** | `SELECT * FROM pg_statio_user_indexes WHERE tablename = 'job_listings_golden';` |
| **Monitor reindex** | `SELECT query FROM pg_stat_activity WHERE query LIKE '%REINDEX%';` |
| **Backup table** | `pg_dump ... --table=job_listings_golden > backup.dump` |

## Summary

1. **Run the fix:** `python fix_index_corruption.py` or `psql -f fix_index_corruption.sql`
2. **Wait for completion** (2-10 minutes)
3. **Verify the fix:** Query the table to ensure it works
4. **Run cleanup:** Use the Data Cleanup API/UI to proceed with data cleanup

The vast majority of index corruption issues are resolved by running REINDEX TABLE CONCURRENTLY. In very rare cases, you may need to restore from backup or contact PostgreSQL support.
