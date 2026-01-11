# Data Cleanup Guide

Complete guide for cleaning up golden job listings data and maintaining data quality.

## Overview

This guide covers:
1. **Data Quality Issues** - Common problems in the dataset
2. **Cleanup Solution** - SQL-based fixes and API endpoints
3. **UI Interface** - How to use the cleanup dashboard
4. **Running Cleanups** - Manual and automated approaches
5. **Monitoring** - Tracking data quality metrics

## Data Quality Issues

The golden job listings table contains several data quality issues from the AI enrichment process:

### 1. Invalid Location Data
**Problem:** Location fields contain placeholder values
- `"None"`, `"NONE"`, `"none"` (string representations)
- Empty strings
- `"NULL"`, `"null"` (string representations)
- `"N/A"`, `"n/a"`

**Impact:**
- Affects: `location_city`, `location_country`, `location_state`, `job_location_normalized`
- Prevents accurate location-based filtering and aggregation
- Skews geographic data analysis

**Example:**
```sql
-- Before cleanup
SELECT location_city, location_country, COUNT(*)
FROM job_listings_golden
WHERE enrichment_status = 'completed'
GROUP BY location_city, location_country
ORDER BY count DESC;

-- Results show:
-- "None" | "None" | 1234
-- "NONE" | "India" | 456
-- "" | "NULL" | 789
```

### 2. Pipe-Separated Values (AI Guessing)
**Problem:** When AI cannot determine a single value, it lists multiple options
- Format: `"value1|value2|value3"`
- Indicates uncertainty in data extraction/enrichment

**Affected Fields:**
- `location_city`, `location_country`, `location_state`
- `seniority_level_normalized`
- `company_industry`, `company_size`
- `primary_role`, `role_category`
- `employment_type_normalized`
- `work_arrangement_normalized`
- `job_role`, `company_title`

**Impact:**
- Cannot be used in queries or aggregations
- Breaks foreign key relationships
- Breaks filtering logic

**Example:**
```sql
-- Problematic data
UPDATE job_listings_golden
SET seniority_level_normalized = 'Mid-Level Engineer|Senior Engineer|Principal Engineer'
WHERE id = 123;

-- After cleanup, takes first value:
-- seniority_level_normalized = 'Mid-Level Engineer'
```

### 3. Excess Whitespace
**Problem:** Extra spaces around data values
- Leading/trailing spaces
- Multiple spaces between words

**Impact:**
- Prevents exact matching
- Creates duplicate entries in GROUP BY clauses
- Inconsistent data representation

## Cleanup Solution

### Migration-Based Cleanup

The cleanup is implemented as a database migration: `004_cleanup_golden_job_listings.py`

**Key Features:**
- Atomic transaction - all or nothing
- Idempotent - safe to run multiple times
- Only targets completed enrichments
- No downtime required (uses CONCURRENTLY)

**Operations Performed:**

1. **NULL Standardization**
   - Converts string placeholders to actual NULL values
   - Targets all relevant fields

   ```sql
   UPDATE job_listings_golden
   SET location_city = NULL
   WHERE location_city IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
   ```

2. **Pipe-Separated Value Handling**
   - Extracts first value using SPLIT_PART
   - Removes remaining options

   ```sql
   UPDATE job_listings_golden
   SET location_city = TRIM(SPLIT_PART(location_city, '|', 1))
   WHERE location_city LIKE '%|%'
     AND location_city IS NOT NULL
     AND location_city NOT IN ('', 'None', 'NULL');
   ```

3. **Whitespace Trimming**
   - Removes leading/trailing spaces
   - Converts empty strings to NULL

   ```sql
   UPDATE job_listings_golden
   SET location_city = NULLIF(TRIM(location_city), '')
   WHERE enrichment_status = 'completed';
   ```

### Running the Migration

**Option 1: During Application Startup**
```bash
# In workflow-svc directory
python migrate.py

# Or manually
alembic upgrade head
```

**Option 2: Manual Migration Run**
```bash
cd workflow-svc
alembic upgrade +1  # Run one migration
# or
alembic upgrade 004_cleanup_golden_job_listings
```

## API Endpoints

The cleanup functionality is exposed via REST API endpoints.

### 1. Check Data Quality Status

**Endpoint:** `GET /api/data-cleanup/status`

**Description:** Get current data quality metrics

**Response:**
```json
{
  "total_rows": 15234,
  "rows_with_null_locations": 2341,
  "rows_with_pipe_separated_values": 1456,
  "rows_with_none_values": 892,
  "null_location_percentage": 15.37,
  "pipe_separated_percentage": 9.56,
  "data_quality_score": 75.07
}
```

**Data Quality Score Interpretation:**
- 95-100: Excellent (clean data)
- 80-95: Good (minor issues)
- 60-80: Fair (notable issues)
- <60: Poor (significant cleanup needed)

### 2. Run Cleanup Operations

**Endpoint:** `POST /api/data-cleanup/run`

**Description:** Execute cleanup operations (can be dry run)

**Request Body:**
```json
{
  "include_whitespace_trim": true,
  "include_pipe_separation": true,
  "include_null_standardization": true,
  "dry_run": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Data cleanup completed successfully",
  "rows_updated": 4689,
  "execution_time_ms": 2340.56,
  "operations": {
    "null_standardization": {
      "rows_updated": 892,
      "fields_processed": 13
    },
    "pipe_separation": {
      "rows_updated": 1456,
      "fields_processed": 13
    },
    "whitespace_trim": {
      "rows_updated": 2341
    }
  },
  "timestamp": "2026-01-10T15:30:45.123Z"
}
```

### 3. Cleanup + Refresh (Recommended)

**Endpoint:** `POST /api/data-cleanup/cleanup-and-refresh`

**Description:** Run cleanup AND refresh materialized views in one operation

**Request Body:**
```json
{
  "include_whitespace_trim": true,
  "include_pipe_separation": true,
  "include_null_standardization": true,
  "dry_run": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Data cleanup and materialized view refresh completed",
  "cleanup_results": { ... },
  "view_refresh_status": "success",
  "timestamp": "2026-01-10T15:30:45.123Z"
}
```

### 4. Refresh Materialized View

**Endpoint:** `POST /api/data-cleanup/refresh-materialized-view`

**Description:** Refresh `mv_root_data` view (use after manual cleanup)

**Response:**
```json
{
  "success": true,
  "message": "Materialized view refreshed successfully",
  "execution_time_ms": 1234.56,
  "timestamp": "2026-01-10T15:30:45.123Z"
}
```

### 5. Get Cleanup History

**Endpoint:** `GET /api/data-cleanup/cleanup-history`

**Description:** Get cleanup operations from last 24 hours

**Response:**
```json
{
  "cleanup_history": [
    {
      "hour": "2026-01-10T15:00:00Z",
      "rows_updated": 2341,
      "last_update": "2026-01-10T15:30:45Z"
    },
    {
      "hour": "2026-01-10T14:00:00Z",
      "rows_updated": 1234,
      "last_update": "2026-01-10T14:25:30Z"
    }
  ],
  "timestamp": "2026-01-10T15:35:00Z"
}
```

## UI Interface

### Accessing the Cleanup Dashboard

1. Open the application in your browser
2. Navigate to sidebar → System → **Data Cleanup**
3. Or go directly to: `http://localhost:5173/cleanup`

### Dashboard Features

#### 1. Data Quality Status Card
Shows real-time metrics:
- **Data Quality Score** (0-100) with color-coded progress bar
- **Total Rows** in golden table
- **Null Locations** - rows with invalid location data
- **Pipe-Separated Values** - rows with AI guesses
- **'None' Values** - rows with string placeholders

#### 2. Run Cleanup Card
Execute cleanup operations:
- **Dry Run Button** - Test changes without modifying data
- **Run Cleanup Button** - Execute cleanup and refresh views
- Displays cleanup results including rows updated and time taken
- Shows specific operations performed

#### 3. Recent Activity Card
Displays cleanup history from last 24 hours:
- Timestamp of each cleanup operation
- Number of rows updated per operation
- Status indicators

#### 4. API Reference Card
Lists available API endpoints:
- Status endpoint (GET)
- Run cleanup endpoint (POST)
- Cleanup and refresh endpoint (POST)
- Refresh view endpoint (POST)
- History endpoint (GET)

### Using the Interface

**Step 1: Check Current Status**
1. Navigate to Data Cleanup page
2. Click "Refresh" button to get latest metrics
3. Review data quality score and problem areas

**Step 2: Perform Dry Run (Recommended)**
1. Click "Dry Run" button
2. Review results without making changes
3. See how many rows would be updated

**Step 3: Run Cleanup**
1. Once confident, click "Run Cleanup" button
2. Wait for operation to complete
3. Status automatically refreshes with new metrics

**Step 4: Monitor Results**
1. Check "Recent Cleanup Activity" section
2. Verify cleanup history
3. Monitor data quality score improvement

## Running Cleanups Programmatically

### Python Example

```python
import requests
import time

API_BASE = "http://localhost:8001/api/data-cleanup"

# 1. Check status
response = requests.get(f"{API_BASE}/status")
status = response.json()
print(f"Data Quality Score: {status['data_quality_score']}%")

# 2. Run cleanup with dry run first
print("\n=== DRY RUN ===")
response = requests.post(
    f"{API_BASE}/run",
    json={
        "dry_run": True,
        "include_whitespace_trim": True,
        "include_pipe_separation": True,
        "include_null_standardization": True
    }
)
dry_run_result = response.json()
print(f"Would update {dry_run_result['rows_updated']} rows")

# 3. Run actual cleanup
print("\n=== RUNNING CLEANUP ===")
response = requests.post(
    f"{API_BASE}/cleanup-and-refresh",
    json={
        "dry_run": False,
        "include_whitespace_trim": True,
        "include_pipe_separation": True,
        "include_null_standardization": True
    }
)
result = response.json()
print(f"Updated {result['cleanup_results']['rows_updated']} rows")
print(f"Execution time: {result['cleanup_results']['execution_time_ms']}ms")

# 4. Check new status
time.sleep(2)  # Wait for materialized view refresh
response = requests.get(f"{API_BASE}/status")
new_status = response.json()
print(f"\nNew Data Quality Score: {new_status['data_quality_score']}%")
improvement = new_status['data_quality_score'] - status['data_quality_score']
print(f"Improvement: {improvement:+.2f}%")
```

### cURL Example

**Check Status:**
```bash
curl http://localhost:8001/api/data-cleanup/status
```

**Dry Run:**
```bash
curl -X POST http://localhost:8001/api/data-cleanup/run \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": true,
    "include_whitespace_trim": true,
    "include_pipe_separation": true,
    "include_null_standardization": true
  }'
```

**Run Cleanup:**
```bash
curl -X POST http://localhost:8001/api/data-cleanup/cleanup-and-refresh \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "include_whitespace_trim": true,
    "include_pipe_separation": true,
    "include_null_standardization": true
  }'
```

## Scheduled Cleanup

### Using a Cron Job

Create a cleanup script (`cleanup.py`):
```python
#!/usr/bin/env python3
import requests
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

API_BASE = "http://localhost:8001/api/data-cleanup"

try:
    logging.info("Starting scheduled cleanup...")

    # Check status first
    response = requests.get(f"{API_BASE}/status")
    status = response.json()

    if status['data_quality_score'] < 90:
        logging.info(f"Quality score {status['data_quality_score']}% < 90%, running cleanup")

        response = requests.post(
            f"{API_BASE}/cleanup-and-refresh",
            json={
                "dry_run": False,
                "include_whitespace_trim": True,
                "include_pipe_separation": True,
                "include_null_standardization": True
            }
        )

        if response.ok:
            result = response.json()
            logging.info(f"Cleanup completed. Updated {result['cleanup_results']['rows_updated']} rows")
        else:
            logging.error(f"Cleanup failed: {response.text}")
    else:
        logging.info(f"Quality score {status['data_quality_score']}% is acceptable, skipping cleanup")

except Exception as e:
    logging.error(f"Error: {str(e)}")
```

**Add to Crontab (daily at 2 AM):**
```bash
0 2 * * * /usr/bin/python3 /path/to/cleanup.py >> /var/log/job-gtm-cleanup.log 2>&1
```

## Data Quality Metrics

### What Gets Measured

1. **Total Rows** - Complete job listings in golden table
2. **Null Location Issues** - Problematic location data
3. **Pipe-Separated Values** - AI uncertain selections
4. **'None' String Values** - Placeholder strings
5. **Data Quality Score** - Composite metric (0-100)

### Baseline Expectations

**Before Cleanup:**
- Data Quality Score: 60-75%
- Pipe-separated values: 5-15%
- Null location issues: 10-20%

**After Cleanup:**
- Data Quality Score: 95%+
- Pipe-separated values: <1%
- Null location issues: <2%

### Monitoring Over Time

Track metrics before and after cleanup:

```sql
-- Get cleanup impact statistics
SELECT
    COUNT(*) as total_rows,
    SUM(CASE WHEN location_city IS NULL THEN 1 ELSE 0 END) as null_cities,
    SUM(CASE WHEN location_country IS NULL THEN 1 ELSE 0 END) as null_countries,
    SUM(CASE WHEN seniority_level_normalized LIKE '%|%' THEN 1 ELSE 0 END) as pipe_separated_seniority,
    updated_at
FROM job_listings_golden
WHERE enrichment_status = 'completed'
GROUP BY DATE(updated_at)
ORDER BY updated_at DESC
LIMIT 30;
```

## Troubleshooting

### Issue: Cleanup Fails

**Symptom:** API returns 500 error

**Solution:**
1. Check database connection: `psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm`
2. Verify migration exists: Check `alembic/versions/004_cleanup_golden_job_listings.py`
3. Check logs: `docker logs workflow-svc` or `docker logs api`

### Issue: Materialized View Not Refreshing

**Symptom:** Data looks same after cleanup

**Solution:**
```bash
# Manually refresh view
psql postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm -c \
  "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_root_data;"
```

### Issue: Performance Degradation During Cleanup

**Symptom:** Queries slow down during cleanup

**Solution:**
- Use `dry_run: true` first to estimate impact
- Run cleanup during off-peak hours
- Monitor with: `SELECT * FROM pg_stat_activity;`

### Issue: Data Quality Score Not Improving

**Symptom:** Score stays same after cleanup

**Solution:**
1. Verify cleanup ran successfully (check response)
2. Check if specific fields still have issues:
   ```sql
   SELECT COUNT(*) FROM job_listings_golden
   WHERE location_city IN ('None', 'NONE', 'none')
   AND enrichment_status = 'completed';
   ```
3. Run cleanup again to ensure idempotency

## Best Practices

1. **Always do a dry run first** - Verify changes before making them
2. **Run during off-peak hours** - Minimize impact on users
3. **Monitor the cleanup history** - Track when and what was fixed
4. **Set up automated cleanups** - Daily or weekly scheduled runs
5. **Watch data quality score** - Aim to keep it >95%
6. **Document custom enrichments** - If you add new fields, document what needs cleanup
7. **Test changes in staging first** - Don't run directly on production

## Future Improvements

Potential enhancements to consider:

1. **Confidence-based filtering** - Use `seniority_confidence_score` to prioritize high-confidence data
2. **Domain-specific cleanup** - Custom rules per field based on domain knowledge
3. **ML-based correction** - Use models to pick best option from pipe-separated values
4. **Incremental cleanup** - Run on new data automatically before materialized view refresh
5. **Data profiling** - Generate detailed data quality reports
6. **Automatic correction** - AI-powered field-by-field correction

## Support

For issues or questions:

1. Check this guide's Troubleshooting section
2. Review API logs in `/var/log/` or Docker containers
3. Check database query logs
4. Review cleanup history via `GET /api/data-cleanup/cleanup-history`

## Files Modified/Created

### Backend (API)
- `api/app/routers/data_cleanup.py` - New cleanup API router
- `api/app/main.py` - Updated to include cleanup router

### Database
- `workflow-svc/alembic/versions/004_cleanup_golden_job_listings.py` - New migration

### Frontend
- `ui/src/components/DataCleanup/DataCleanup.tsx` - New cleanup dashboard component
- `ui/src/pages/DataCleanupPage.tsx` - New cleanup page
- `ui/src/App.tsx` - Updated routing
- `ui/src/components/Layout/Sidebar.tsx` - Updated navigation

## Summary

This data cleanup system provides:
- ✅ SQL-based fixes for data quality issues
- ✅ API endpoints for programmatic access
- ✅ Web UI for easy management
- ✅ Dry run capability for safe testing
- ✅ Automatic materialized view refresh
- ✅ Cleanup history tracking
- ✅ Data quality metrics and scoring
- ✅ Flexible and idempotent operations
