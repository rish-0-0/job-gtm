# Index Corruption - Complete Solution Summary

## What Happened

Your database has a corrupted index on the `job_listings_golden` table. This prevents the cleanup operation from running.

```
Error: psycopg2.errors.IndexCorrupted: table tid from new index tuple (1753,7) cannot find insert offset between offsets 13 and 16 of block 20 in index "ix_job_listings_golden_company_title"
```

## Root Cause

The PostgreSQL index became corrupted, likely due to:
- Unexpected server shutdown
- Disk I/O issues
- Concurrent operations interfering with index structure
- Long-running transactions that were interrupted

## Solution

Rebuild all indexes on the table using PostgreSQL's built-in REINDEX command.

## Files Provided

### 1. **FIX_INDEX_CORRUPTION_QUICK_START.md** ⭐ START HERE
Quick 2-minute guide with minimal steps

### 2. **fix_index_corruption.py** (Recommended)
```bash
cd workflow-svc
python fix_index_corruption.py
```
- Automatic detection of issues
- Progress logging
- Verification after fix
- Error handling with fallbacks

### 3. **sql/fix_index_corruption.sql**
```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm \
  -f sql/fix_index_corruption.sql
```
- Direct SQL approach
- No dependencies
- Manual control

### 4. **INDEX_CORRUPTION_FIX_GUIDE.md**
Comprehensive guide with:
- Detailed explanations
- Multiple solutions
- Troubleshooting section
- Prevention strategies
- Recovery procedures

## Implementation Steps

### Step 1: Fix the Corruption (Choose One)

**A) Using Python (Easiest & Recommended):**
```bash
cd workflow-svc
python fix_index_corruption.py
```

**B) Using Direct SQL:**
```sql
REINDEX TABLE CONCURRENTLY job_listings_golden;
VACUUM ANALYZE job_listings_golden;
```

**C) Using SQL File:**
```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm \
  -f sql/fix_index_corruption.sql
```

### Step 2: Wait for Completion

The operation takes 2-10 minutes. You'll see logs indicating:
- Index rebuild starting
- Index rebuild completing
- Verification results
- Statistics update

### Step 3: Verify the Fix

```bash
# Check index health
curl http://localhost:8001/api/data-cleanup/check-index-health

# Should return: "healthy": true
```

### Step 4: Run Cleanup

```bash
curl -X POST http://localhost:8001/api/data-cleanup/cleanup-and-refresh \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

Or use UI: `http://localhost:5173/cleanup` → "Run Cleanup"

## API Enhancements

### New Endpoint: Check Index Health

```bash
GET /api/data-cleanup/check-index-health
```

Returns:
```json
{
  "healthy": true,
  "message": "All indexes are accessible",
  "indexes": [
    {
      "name": "ix_job_listings_golden_company_title",
      "blocks_read": 1523,
      "blocks_hit": 45230,
      "status": "Heavily used"
    }
  ],
  "total_indexes": 7
}
```

### Enhanced Error Messages

When cleanup fails due to index issues, the API now:
- ✅ Detects index corruption
- ✅ Returns 503 Service Unavailable (instead of 500)
- ✅ Suggests running the fix script
- ✅ Provides step-by-step instructions

## What Gets Fixed

When you run REINDEX:

✅ **Rebuilds 7 indexes:**
1. `ix_job_listings_golden_source_job_id`
2. `ix_job_listings_golden_company_title` ← (the corrupted one)
3. `ix_job_listings_golden_scraper_source`
4. `ix_job_listings_golden_enrichment_status`
5. `ix_job_listings_golden_detail_scrape_status`
6. `ix_job_listings_golden_seniority_level_normalized`
7. `ix_job_listings_golden_posting_url` (unique index)

✅ **Fixes corruption** in B-tree structures
✅ **Preserves all data** (only indexes are rebuilt)
✅ **Maintains concurrent access** (no table locks)
✅ **Updates table statistics** (improves query performance)

## Performance Impact

### During Reindex (2-10 minutes)
- **Disk I/O:** High
- **Memory:** Moderate increase
- **CPU:** High utilization
- **Table Access:** Still readable (writes slower)
- **Downtime:** None

### After Reindex
- **Query Performance:** Normal or improved
- **Data Integrity:** Verified
- **Cleanup Operations:** Now possible

## Prevention

To prevent future corruption:

1. **Regular maintenance** (weekly):
   ```bash
   psql -c "VACUUM ANALYZE job_listings_golden;"
   ```

2. **Monitor index health** (monthly):
   ```bash
   curl http://localhost:8001/api/data-cleanup/check-index-health
   ```

3. **Keep PostgreSQL updated** (security & stability)

4. **Ensure proper shutdown** (never force-kill PostgreSQL)

5. **Monitor disk space** (maintain 20%+ free space)

## Rollback Plan

If fixing the indexes causes issues:

1. **Restore from backup:**
   ```bash
   pg_restore -d jobgtm backup.dump
   ```

2. **Contact PostgreSQL support** (rare)

3. **Upgrade/downgrade PostgreSQL** (if it's a known bug)

## Testing

### Before Running Cleanup
```bash
# 1. Check index health
curl http://localhost:8001/api/data-cleanup/check-index-health

# 2. Check table accessibility
curl http://localhost:8001/api/data-cleanup/status

# 3. Run dry run
curl -X POST http://localhost:8001/api/data-cleanup/run \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### After Fix
All above commands should work without errors.

## Troubleshooting

### Problem: Reindex Still Shows Errors
**Solution:** See "Troubleshooting" section in INDEX_CORRUPTION_FIX_GUIDE.md

### Problem: Reindex Takes Too Long
**Solution:** This is normal for large tables. Monitor progress:
```sql
SELECT query FROM pg_stat_activity WHERE query LIKE '%REINDEX%';
```

### Problem: Cannot Connect to Database
**Solution:** Make sure PostgreSQL is running:
```bash
# Check status
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm -c "SELECT 1;"
```

## Summary

| Step | Time | Command |
|------|------|---------|
| **1. Fix corruption** | 2-10 min | `python fix_index_corruption.py` |
| **2. Verify fix** | 1 min | `curl .../check-index-health` |
| **3. Run cleanup** | 5-30 min | `curl .../cleanup-and-refresh` |
| **Total** | **10-40 min** | |

## Files Modified/Created

### New Files
- `fix_index_corruption.py` - Python fix script
- `sql/fix_index_corruption.sql` - SQL fix script
- `INDEX_CORRUPTION_FIX_GUIDE.md` - Detailed guide
- `FIX_INDEX_CORRUPTION_QUICK_START.md` - Quick start
- `INDEX_CORRUPTION_SUMMARY.md` - This file

### Modified Files
- `api/app/routers/data_cleanup.py` - Added:
  - Better error detection
  - Index corruption handling
  - New `/check-index-health` endpoint
  - Clear recovery instructions

## Next Steps

1. **Read:** FIX_INDEX_CORRUPTION_QUICK_START.md
2. **Run:** `cd workflow-svc && python fix_index_corruption.py`
3. **Wait:** For reindex to complete (5-10 minutes)
4. **Verify:** `curl http://localhost:8001/api/data-cleanup/check-index-health`
5. **Cleanup:** Use Data Cleanup UI or API

---

**Timeline:**
- ⏱️ Right now: Pick a fix method (1 min)
- ⏱️ Next 10 minutes: Run the fix script
- ⏱️ After that: Run the cleanup operation (5-30 min)

**Questions?**
See INDEX_CORRUPTION_FIX_GUIDE.md for detailed troubleshooting and explanations.
