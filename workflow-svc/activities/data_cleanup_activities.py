"""
Data Cleanup Activities for Temporal Workflows
Handles index verification, repair, and data cleanup operations
"""
import logging
import time
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from temporalio import activity

logger = logging.getLogger(__name__)


class DataCleanupActivities:
    """Activities for data cleanup workflow"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)

    @activity.defn
    async def verify_index_health(self) -> dict:
        """
        Verify the health of indexes on job_listings_golden table

        Returns:
            dict with health status, list of indexes, and any corruption details
        """
        logger.info("[IndexVerification] Starting index health check...")

        session = self.SessionLocal()
        try:
            # Get all indexes on the table
            result = session.execute(text("""
                SELECT
                    indexname,
                    indexdef,
                    idx_blks_read,
                    idx_blks_hit
                FROM pg_indexes i
                LEFT JOIN pg_statio_user_indexes s ON i.indexname = s.indexname
                WHERE i.tablename = 'job_listings_golden'
                ORDER BY i.indexname
            """)).fetchall()

            if not result:
                logger.warning("[IndexVerification] No indexes found on table!")
                return {
                    "healthy": False,
                    "corrupted": True,
                    "reason": "No indexes found on job_listings_golden table",
                    "indexes": []
                }

            indexes = []
            corrupted = False
            corruption_details = []

            for idx_name, idx_def, blks_read, blks_hit in result:
                idx_info = {
                    "name": idx_name,
                    "blocks_read": blks_read or 0,
                    "blocks_hit": blks_hit or 0,
                    "accessible": True
                }
                indexes.append(idx_info)
                logger.info(f"[IndexVerification] Index {idx_name}: accessible, "
                           f"{blks_read or 0} blocks read, {blks_hit or 0} hits")

            # Try to access the table to detect corruption
            try:
                count = session.execute(text("""
                    SELECT COUNT(*) FROM job_listings_golden
                    WHERE enrichment_status = 'completed'
                """)).scalar()
                logger.info(f"[IndexVerification] Table accessible: {count:,} completed rows")
            except Exception as e:
                error_str = str(e)
                if "IndexCorrupted" in error_str or "index" in error_str.lower():
                    logger.error(f"[IndexVerification] Index corruption detected: {error_str}")
                    corrupted = True
                    corruption_details.append(error_str)

            return {
                "healthy": not corrupted,
                "corrupted": corrupted,
                "corruption_details": corruption_details,
                "indexes": indexes,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            error_str = str(e)
            logger.error(f"[IndexVerification] Error during health check: {error_str}")

            # Check if it's a corruption error
            if "IndexCorrupted" in error_str or "index" in error_str.lower():
                return {
                    "healthy": False,
                    "corrupted": True,
                    "reason": error_str,
                    "indexes": []
                }

            raise

        finally:
            session.close()

    @activity.defn
    async def repair_indexes(self) -> dict:
        """
        Repair corrupted indexes on job_listings_golden table

        Uses REINDEX TABLE CONCURRENTLY to rebuild indexes without blocking table access

        Returns:
            dict with repair status and details
        """
        logger.info("[IndexRepair] Starting index repair...")

        session = self.SessionLocal()
        start_time = time.time()

        try:
            logger.info("[IndexRepair] Running REINDEX TABLE CONCURRENTLY...")
            session.execute(text("REINDEX TABLE CONCURRENTLY job_listings_golden"))
            session.commit()
            logger.info("[IndexRepair] REINDEX completed successfully")

            logger.info("[IndexRepair] Running VACUUM ANALYZE...")
            # Close the session before VACUUM (requires isolation level 0)
            session.close()
            session = self.SessionLocal()

            # Manually execute VACUUM ANALYZE outside transaction
            with self.engine.connect() as conn:
                conn.connection.set_isolation_level(0)
                conn.execute(text("VACUUM ANALYZE job_listings_golden"))
                conn.connection.set_isolation_level(1)

            logger.info("[IndexRepair] VACUUM ANALYZE completed successfully")

            # Verify the repair
            session = self.SessionLocal()
            count = session.execute(text("""
                SELECT COUNT(*) FROM job_listings_golden
                WHERE enrichment_status = 'completed'
            """)).scalar()

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(f"[IndexRepair] Repair completed in {execution_time_ms:.1f}ms. "
                       f"Table verified: {count:,} rows")

            return {
                "success": True,
                "message": "Index repair completed successfully",
                "execution_time_ms": round(execution_time_ms, 2),
                "rows_verified": count,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            error_str = str(e)
            logger.error(f"[IndexRepair] Error during repair: {error_str}")
            session.rollback()

            # Check if the error is still corruption-related
            if "IndexCorrupted" in error_str or "index" in error_str.lower():
                logger.error("[IndexRepair] Index corruption persists after REINDEX CONCURRENT. "
                            "Attempting non-concurrent reindex...")
                try:
                    # Non-concurrent reindex (slower but more thorough)
                    session = self.SessionLocal()
                    session.execute(text("REINDEX TABLE job_listings_golden"))
                    session.commit()
                    logger.info("[IndexRepair] Non-concurrent REINDEX completed")

                    return {
                        "success": True,
                        "message": "Index repair completed with non-concurrent reindex",
                        "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                except Exception as e2:
                    logger.error(f"[IndexRepair] Non-concurrent reindex also failed: {e2}")
                    return {
                        "success": False,
                        "error": str(e2),
                        "message": "Index repair failed even with non-concurrent reindex"
                    }

            raise

        finally:
            session.close()

    @activity.defn
    async def cleanup_job_listings_data(
        self,
        include_null_standardization: bool = True,
        include_pipe_separation: bool = True,
        include_whitespace_trim: bool = True
    ) -> dict:
        """
        Clean up golden job listings data

        Operations:
        1. Standardize NULL values (None, NONE, null, etc. -> NULL)
        2. Fix pipe-separated values (a|b|c -> a)
        3. Trim excess whitespace

        Args:
            include_null_standardization: Whether to standardize NULL values
            include_pipe_separation: Whether to fix pipe-separated values
            include_whitespace_trim: Whether to trim whitespace

        Returns:
            dict with cleanup status and statistics
        """
        logger.info("[DataCleanup] Starting data cleanup...")

        session = self.SessionLocal()
        start_time = time.time()
        operations = {}
        total_rows_updated = 0

        try:
            # Fields to clean
            cleanup_fields = [
                'location_city', 'location_state', 'location_country',
                'job_location_normalized', 'seniority_level_normalized',
                'work_arrangement_normalized', 'company_industry', 'company_size',
                'primary_role', 'role_category', 'employment_type_normalized',
                'job_role', 'company_title'
            ]

            # Operation 1: Standardize NULL values
            if include_null_standardization:
                logger.info("[DataCleanup] Standardizing NULL values...")
                null_updates = 0

                for field in cleanup_fields:
                    result = session.execute(text(f"""
                        UPDATE job_listings_golden
                        SET {field} = NULL, updated_at = NOW()
                        WHERE enrichment_status = 'completed'
                        AND {field} IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a')
                    """))
                    null_updates += result.rowcount

                session.commit()
                operations['null_standardization'] = {
                    'rows_updated': null_updates,
                    'fields_processed': len(cleanup_fields)
                }
                total_rows_updated += null_updates
                logger.info(f"[DataCleanup] Standardized NULL values in {null_updates} rows")

            # Operation 2: Fix pipe-separated values
            if include_pipe_separation:
                logger.info("[DataCleanup] Processing pipe-separated values...")
                pipe_updates = 0

                for field in cleanup_fields:
                    result = session.execute(text(f"""
                        UPDATE job_listings_golden
                        SET {field} = TRIM(SPLIT_PART({field}, '|', 1)), updated_at = NOW()
                        WHERE enrichment_status = 'completed'
                        AND {field} LIKE '%|%'
                        AND {field} IS NOT NULL
                        AND {field} NOT IN ('', 'None', 'NULL')
                    """))
                    pipe_updates += result.rowcount

                session.commit()
                operations['pipe_separation'] = {
                    'rows_updated': pipe_updates,
                    'fields_processed': len(cleanup_fields)
                }
                total_rows_updated += pipe_updates
                logger.info(f"[DataCleanup] Fixed pipe-separated values in {pipe_updates} rows")

            # Operation 3: Trim whitespace
            if include_whitespace_trim:
                logger.info("[DataCleanup] Trimming excess whitespace...")

                trim_sql = "UPDATE job_listings_golden SET "
                trim_sql += ", ".join([f"{field} = NULLIF(TRIM({field}), '')"
                                      for field in cleanup_fields])
                trim_sql += ", updated_at = NOW() WHERE enrichment_status = 'completed'"

                result = session.execute(text(trim_sql))
                whitespace_updates = result.rowcount
                session.commit()

                operations['whitespace_trim'] = {
                    'rows_updated': whitespace_updates
                }
                total_rows_updated += whitespace_updates
                logger.info(f"[DataCleanup] Trimmed whitespace in {whitespace_updates} rows")

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(f"[DataCleanup] Data cleanup completed. "
                       f"Updated {total_rows_updated} rows in {execution_time_ms:.1f}ms")

            return {
                "success": True,
                "message": "Data cleanup completed successfully",
                "rows_updated": total_rows_updated,
                "execution_time_ms": round(execution_time_ms, 2),
                "operations": operations,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"[DataCleanup] Error during cleanup: {str(e)}")
            session.rollback()
            raise

        finally:
            session.close()

    @activity.defn(name="data_cleanup_refresh_view")
    async def refresh_materialized_view(self) -> dict:
        """
        Refresh the materialized view after cleanup

        Refreshes mv_root_data which is used by the API for querying

        Returns:
            dict with refresh status
        """
        logger.info("[ViewRefresh] Refreshing materialized view...")

        session = self.SessionLocal()
        start_time = time.time()

        try:
            logger.info("[ViewRefresh] Executing REFRESH MATERIALIZED VIEW CONCURRENTLY...")
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_root_data"))
            session.commit()

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(f"[ViewRefresh] Materialized view refreshed in {execution_time_ms:.1f}ms")

            return {
                "success": True,
                "message": "Materialized view refreshed successfully",
                "execution_time_ms": round(execution_time_ms, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"[ViewRefresh] Error refreshing materialized view: {str(e)}")
            session.rollback()
            raise

        finally:
            session.close()

    @activity.defn
    async def normalize_salaries_to_usd(self) -> dict:
        """
        Normalize all salaries to USD

        Converts salaries from various currencies (INR, EUR, GBP, etc.) to USD.
        Only processes rows that haven't been normalized yet (currency_conversion_date IS NULL).
        This ensures running the workflow multiple times won't keep converting already-normalized salaries.

        SPECIAL HANDLING FOR INDIAN SALARIES:
        Indian salaries are in monthly rupees. This function:
        1. Updates min_salary_raw and max_salary_raw: multiplies by 12 (monthly → annual INR)
        2. Updates min_salary_usd and max_salary_usd: divides by 80 (annual INR → annual USD)
        Example: 25,000 INR/month → 300,000 INR/year → $3,750 USD/year

        Currency detection:
        1. Uses currency_raw if available
        2. Infers from location_country (e.g., India -> INR, USA -> USD)
        3. Checks salary_range_raw for currency symbols (₹, $, €, £)

        Returns:
            dict with normalization status and statistics
        """
        logger.info("[SalaryNormalization] Starting salary normalization...")

        session = self.SessionLocal()
        start_time = time.time()

        try:
            # Execute the normalization SQL
            logger.info("[SalaryNormalization] Detecting currencies and converting to USD...")
            logger.info("[SalaryNormalization] Indian salaries: monthly INR * 12 / 80 = annual USD")

            result = session.execute(text("""
                WITH currency_rates AS (
                    SELECT 'INR' AS currency, 80.0 AS rate_to_usd, true AS is_monthly
                    UNION ALL SELECT 'USD', 1.0, false
                    UNION ALL SELECT 'EUR', 0.92, false
                    UNION ALL SELECT 'GBP', 0.79, false
                    UNION ALL SELECT 'CAD', 1.36, false
                    UNION ALL SELECT 'AUD', 1.52, false
                    UNION ALL SELECT 'SGD', 1.35, false
                    UNION ALL SELECT 'JPY', 149.0, false
                    UNION ALL SELECT 'CNY', 7.24, false
                ),
                detected_currency AS (
                    SELECT
                        id,
                        min_salary_raw,
                        max_salary_raw,
                        CASE
                            WHEN currency_raw IN ('INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'SGD', 'JPY', 'CNY') THEN currency_raw
                            WHEN currency_raw LIKE '{%}' THEN TRIM(BOTH '{}' FROM currency_raw)
                            WHEN location_country IN ('India', 'india') THEN 'INR'
                            WHEN location_country IN ('USA', 'United States', 'US', 'United States of America') THEN 'USD'
                            WHEN location_country IN ('UK', 'United Kingdom', 'England', 'Scotland', 'Wales', 'Great Britain') THEN 'GBP'
                            WHEN location_country IN ('Canada') THEN 'CAD'
                            WHEN location_country IN ('Australia') THEN 'AUD'
                            WHEN location_country IN ('Singapore') THEN 'SGD'
                            WHEN location_country IN ('Japan') THEN 'JPY'
                            WHEN location_country IN ('China') THEN 'CNY'
                            WHEN salary_range_raw LIKE '%₹%' OR salary_range_raw LIKE '%Rs%' OR salary_range_raw LIKE '%INR%' THEN 'INR'
                            WHEN salary_range_raw LIKE '%$%' OR salary_range_raw LIKE '%USD%' THEN 'USD'
                            WHEN salary_range_raw LIKE '%€%' OR salary_range_raw LIKE '%EUR%' THEN 'EUR'
                            WHEN salary_range_raw LIKE '%£%' OR salary_range_raw LIKE '%GBP%' THEN 'GBP'
                            ELSE 'USD'
                        END AS detected_currency,
                        currency_raw AS original_currency_raw
                    FROM job_listings_golden
                    WHERE enrichment_status = 'completed'
                      AND min_salary_raw IS NOT NULL
                      AND currency_conversion_date IS NULL
                )
                UPDATE job_listings_golden
                SET
                    -- Update raw salary fields for Indian jobs (monthly to annual)
                    min_salary_raw = CASE
                        WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
                        THEN dc.min_salary_raw * 12
                        ELSE dc.min_salary_raw
                    END,
                    max_salary_raw = CASE
                        WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
                        THEN dc.max_salary_raw * 12
                        ELSE dc.max_salary_raw
                    END,
                    -- Calculate USD values
                    min_salary_usd = ROUND(
                        CASE
                            WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
                            THEN (dc.min_salary_raw * 12) / cr.rate_to_usd
                            ELSE dc.min_salary_raw / cr.rate_to_usd
                        END, 2
                    ),
                    max_salary_usd = ROUND(
                        CASE
                            WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
                            THEN (dc.max_salary_raw * 12) / cr.rate_to_usd
                            ELSE dc.max_salary_raw / cr.rate_to_usd
                        END, 2
                    ),
                    currency_conversion_rate = cr.rate_to_usd,
                    currency_conversion_date = NOW(),
                    currency_raw = CASE
                        WHEN dc.original_currency_raw IS NULL OR dc.original_currency_raw LIKE '{%}'
                        THEN dc.detected_currency
                        ELSE dc.original_currency_raw
                    END,
                    updated_at = NOW()
                FROM detected_currency dc
                JOIN currency_rates cr ON cr.currency = dc.detected_currency
                WHERE job_listings_golden.id = dc.id
            """))

            rows_updated = result.rowcount
            session.commit()

            # Get statistics on normalized salaries
            stats = session.execute(text("""
                SELECT
                    COALESCE(currency_raw, 'Unknown') as currency_raw,
                    COUNT(*) as count,
                    ROUND(AVG(min_salary_usd), 2) as avg_min_salary_usd,
                    ROUND(AVG(max_salary_usd), 2) as avg_max_salary_usd
                FROM job_listings_golden
                WHERE enrichment_status = 'completed'
                  AND currency_conversion_date IS NOT NULL
                GROUP BY currency_raw
                ORDER BY count DESC
            """)).fetchall()

            currency_stats = {}
            for currency, count, avg_min, avg_max in stats:
                # Ensure all values are JSON-serializable (handle None)
                currency_key = str(currency) if currency is not None else 'Unknown'
                currency_stats[currency_key] = {
                    'count': int(count) if count is not None else 0,
                    'avg_min_salary_usd': float(avg_min) if avg_min is not None else 0.0,
                    'avg_max_salary_usd': float(avg_max) if avg_max is not None else 0.0
                }

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(f"[SalaryNormalization] Normalized {rows_updated} salaries in {execution_time_ms:.1f}ms")
            logger.info(f"[SalaryNormalization] Currency breakdown: {currency_stats}")

            return {
                "success": True,
                "message": f"Successfully normalized {rows_updated} salaries to USD",
                "rows_updated": int(rows_updated),
                "currency_stats": currency_stats,
                "execution_time_ms": float(round(execution_time_ms, 2)),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"[SalaryNormalization] Error during normalization: {str(e)}")
            session.rollback()
            raise

        finally:
            session.close()
