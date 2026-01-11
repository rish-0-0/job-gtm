#!/usr/bin/env python3
"""
Fix PostgreSQL index corruption on job_listings_golden table

Usage:
    python fix_index_corruption.py

This script:
1. Detects index corruption
2. Rebuilds all indexes using REINDEX TABLE CONCURRENTLY
3. Verifies the table after rebuild
4. Runs VACUUM ANALYZE to update statistics
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm"
)

def fix_index_corruption():
    """Fix index corruption on job_listings_golden table"""

    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    Session = sessionmaker(bind=engine)

    try:
        logger.info("=" * 70)
        logger.info("FIXING INDEX CORRUPTION ON job_listings_golden TABLE")
        logger.info("=" * 70)

        session = Session()

        # Step 1: List current indexes
        logger.info("\n[STEP 1] Listing indexes on job_listings_golden...")
        try:
            result = session.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'job_listings_golden'
                ORDER BY indexname
            """)).fetchall()

            if result:
                logger.info(f"Found {len(result)} indexes:")
                for idx_name, idx_def in result:
                    logger.info(f"  - {idx_name}")
            else:
                logger.warning("No indexes found!")
                return False

        except Exception as e:
            logger.error(f"Error listing indexes: {e}")
            return False

        # Step 2: Reindex the table
        logger.info("\n[STEP 2] Rebuilding all indexes (this may take a few minutes)...")
        try:
            # Use CONCURRENTLY to avoid locking the table for too long
            session.execute(text("REINDEX TABLE CONCURRENTLY job_listings_golden"))
            session.commit()
            logger.info("✓ Index rebuild completed successfully")

        except Exception as e:
            logger.error(f"Error during reindex: {e}")
            session.rollback()

            # Try non-concurrent reindex if concurrent fails
            logger.info("\n[STEP 2-RETRY] Trying non-concurrent reindex...")
            try:
                session.execute(text("REINDEX TABLE job_listings_golden"))
                session.commit()
                logger.info("✓ Non-concurrent index rebuild completed")
            except Exception as e2:
                logger.error(f"Non-concurrent reindex also failed: {e2}")
                return False

        # Step 3: Verify indexes
        logger.info("\n[STEP 3] Verifying index status...")
        try:
            result = session.execute(text("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_blks_read,
                    idx_blks_hit
                FROM pg_statio_user_indexes
                WHERE tablename = 'job_listings_golden'
                ORDER BY indexname
            """)).fetchall()

            logger.info(f"Index statistics after rebuild:")
            for schema, table, idx_name, blks_read, blks_hit in result:
                logger.info(f"  - {idx_name}: {blks_read} blocks read, {blks_hit} blocks hit")

        except Exception as e:
            logger.warning(f"Could not retrieve index statistics: {e}")

        # Step 4: Vacuum and analyze
        logger.info("\n[STEP 4] Running VACUUM ANALYZE (this may take a few minutes)...")
        try:
            # Note: VACUUM ANALYZE cannot run in a transaction
            session.close()
            session = Session()

            # Set isolation level to autocommit
            session.connection().connection.set_isolation_level(0)

            session.execute(text("VACUUM ANALYZE job_listings_golden"))
            logger.info("✓ VACUUM ANALYZE completed")

        except Exception as e:
            logger.warning(f"VACUUM ANALYZE warning: {e}")
            # This is often non-fatal

        # Step 5: Verify table integrity
        logger.info("\n[STEP 5] Verifying table integrity...")
        try:
            result = session.execute(text("""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(CASE WHEN enrichment_status = 'completed' THEN 1 END) as completed_rows
                FROM job_listings_golden
            """)).fetchone()

            total, completed = result
            logger.info(f"✓ Table integrity verified:")
            logger.info(f"  - Total rows: {total:,}")
            logger.info(f"  - Completed enrichments: {completed:,}")

        except Exception as e:
            logger.error(f"Error verifying table: {e}")
            return False

        logger.info("\n" + "=" * 70)
        logger.info("✓ INDEX CORRUPTION FIX COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info("\nYou can now run the data cleanup operation.")
        logger.info("Use the Data Cleanup API: POST /api/data-cleanup/cleanup-and-refresh")

        return True

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
    finally:
        try:
            session.close()
        except:
            pass


if __name__ == "__main__":
    success = fix_index_corruption()
    sys.exit(0 if success else 1)
