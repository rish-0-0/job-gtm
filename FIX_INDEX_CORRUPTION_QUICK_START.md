# Quick Start: Fix Index Corruption

## Error You're Getting

```
psycopg2.errors.IndexCorrupted: table tid from new index tuple... in index "ix_job_listings_golden_..."
```

## 2-Minute Fix

### Option 1: Using Python Script (Recommended)

```bash
cd workflow-svc
python fix_index_corruption.py
```

That's it! The script will:
- ✅ Rebuild all indexes (2-10 minutes)
- ✅ Verify the fix
- ✅ Update statistics
- ✅ Tell you when it's done

### Option 2: Using SQL (Direct)

```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm
```

Then copy-paste this:

```sql
-- Fix the corruption (takes 2-10 minutes)
REINDEX TABLE CONCURRENTLY job_listings_golden;

-- Update statistics
VACUUM ANALYZE job_listings_golden;

-- Verify it worked
SELECT COUNT(*) FROM job_listings_golden WHERE enrichment_status = 'completed';
```

### Option 3: Using SQL File

```bash
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm \
  -f sql/fix_index_corruption.sql
```

## Check Index Health (Optional)

Before running cleanup, check if indexes are healthy:

```bash
curl http://localhost:8001/api/data-cleanup/check-index-health
```

Response if healthy:
```json
{
  "healthy": true,
  "message": "All indexes are accessible",
  "total_indexes": 7,
  "indexes": [...]
}
```

Response if corrupted:
```json
{
  "healthy": false,
  "message": "Index corruption detected",
  "recovery_steps": [
    "1. Run: cd workflow-svc && python fix_index_corruption.py",
    "2. Or run: psql postgresql://... -f sql/fix_index_corruption.sql",
    "3. Wait for reindex to complete",
    "4. Then retry the cleanup operation"
  ]
}
```

## After Fixing

Run the cleanup:

```bash
curl -X POST http://localhost:8001/api/data-cleanup/cleanup-and-refresh \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

Or use the UI: `http://localhost:5173/cleanup` → Click "Run Cleanup"

## What If It Still Fails?

See `INDEX_CORRUPTION_FIX_GUIDE.md` for detailed troubleshooting.

## Files Available

- `fix_index_corruption.py` - Python script (recommended)
- `sql/fix_index_corruption.sql` - SQL script
- `INDEX_CORRUPTION_FIX_GUIDE.md` - Detailed guide with troubleshooting

## Time Required

- **Reindex operation:** 2-10 minutes (depending on data size)
- **Your action:** 1 minute to run the script
- **Total:** ~5-15 minutes

---

**TL;DR:** Run `cd workflow-svc && python fix_index_corruption.py`, wait for it to finish, then run cleanup again!
