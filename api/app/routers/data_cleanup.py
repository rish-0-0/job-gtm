"""
Data Cleanup Router
Provides endpoints to cleanup and maintain data quality in golden job listings
Uses Temporal workflows for orchestration and error recovery
"""
import logging
import os
import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from temporalio.client import Client

from app.database import get_db
from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-cleanup", tags=["data-cleanup"])

# Temporal configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "job-gtm-queue")


# Workflow Input Model (matches DataCleanupWorkflowInput in workflow-svc)
@dataclass
class DataCleanupWorkflowInput:
    """Input parameters for data cleanup workflow"""
    include_null_standardization: bool = True
    include_pipe_separation: bool = True
    include_whitespace_trim: bool = True
    refresh_materialized_view: bool = True
    skip_index_verification: bool = False


# Request/Response Models
class DataCleanupRequest(BaseModel):
    """Request to cleanup golden job listings data"""
    include_whitespace_trim: bool = True
    include_pipe_separation: bool = True
    include_null_standardization: bool = True
    dry_run: bool = False


class DataCleanupStatus(BaseModel):
    """Status of data quality in golden job listings"""
    total_rows: int
    rows_with_null_locations: int
    rows_with_pipe_separated_values: int
    rows_with_none_values: int
    null_location_percentage: float
    pipe_separated_percentage: float
    data_quality_score: float  # 0-100


@router.get("/status", response_model=DataCleanupStatus)
async def get_data_quality_status(db: Session = Depends(get_db)):
    """
    Get current data quality status of golden job listings

    Returns statistics about data issues that need cleanup
    """
    logger.info("[DataCleanup] Checking data quality status...")

    try:
        # Count total rows
        total_rows = db.execute(
            text("SELECT COUNT(*) FROM job_listings_golden WHERE enrichment_status = 'completed'")
        ).scalar()

        if total_rows == 0:
            return DataCleanupStatus(
                total_rows=0,
                rows_with_null_locations=0,
                rows_with_pipe_separated_values=0,
                rows_with_none_values=0,
                null_location_percentage=0.0,
                pipe_separated_percentage=0.0,
                data_quality_score=100.0
            )

        # Count rows with problematic location data
        null_locations = db.execute(text("""
            SELECT COUNT(*) FROM job_listings_golden
            WHERE enrichment_status = 'completed'
            AND (
                location_city IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A')
                OR location_country IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A')
                OR location_city IS NULL
                OR location_country IS NULL
            )
        """)).scalar()

        # Count rows with pipe-separated values (AI guessing)
        pipe_separated = db.execute(text("""
            SELECT COUNT(*) FROM job_listings_golden
            WHERE enrichment_status = 'completed'
            AND (
                location_city LIKE '%|%'
                OR location_country LIKE '%|%'
                OR seniority_level_normalized LIKE '%|%'
                OR company_industry LIKE '%|%'
                OR primary_role LIKE '%|%'
                OR role_category LIKE '%|%'
                OR employment_type_normalized LIKE '%|%'
                OR company_size LIKE '%|%'
                OR work_arrangement_normalized LIKE '%|%'
            )
        """)).scalar()

        # Count rows with "None" string values
        none_values = db.execute(text("""
            SELECT COUNT(*) FROM job_listings_golden
            WHERE enrichment_status = 'completed'
            AND (
                location_city IN ('None', 'NONE', 'none')
                OR location_country IN ('None', 'NONE', 'none')
                OR seniority_level_normalized IN ('None', 'NONE', 'none')
                OR company_industry IN ('None', 'NONE', 'none')
                OR primary_role IN ('None', 'NONE', 'none')
                OR role_category IN ('None', 'NONE', 'none')
            )
        """)).scalar()

        null_location_pct = (null_locations / total_rows * 100) if total_rows > 0 else 0
        pipe_separated_pct = (pipe_separated / total_rows * 100) if total_rows > 0 else 0
        none_values_pct = (none_values / total_rows * 100) if total_rows > 0 else 0

        # Calculate data quality score (100 - issues)
        issues_score = none_values_pct + pipe_separated_pct
        data_quality_score = max(0, 100 - issues_score)

        logger.info(
            f"[DataCleanup] Data quality: {total_rows} total rows, "
            f"{null_location_pct:.1f}% null locations, "
            f"{pipe_separated_pct:.1f}% pipe-separated, "
            f"{none_values_pct:.1f}% 'None' values, "
            f"Quality Score: {data_quality_score:.1f}%"
        )

        return DataCleanupStatus(
            total_rows=int(total_rows),
            rows_with_null_locations=int(null_locations),
            rows_with_pipe_separated_values=int(pipe_separated),
            rows_with_none_values=int(none_values),
            null_location_percentage=round(null_location_pct, 2),
            pipe_separated_percentage=round(pipe_separated_pct, 2),
            data_quality_score=round(data_quality_score, 2)
        )

    except Exception as e:
        logger.error(f"[DataCleanup] Error checking data quality: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking data quality: {str(e)}")


@router.post("/cleanup-and-refresh")
async def cleanup_and_refresh(request: DataCleanupRequest = DataCleanupRequest()):
    """
    Start a Temporal workflow to cleanup data and refresh materialized views

    Workflow steps:
    1. Verify index health - Check if database indexes are corrupted
    2. Repair indexes (if needed) - Rebuild corrupted indexes using REINDEX
    3. Clean up data - Standardize NULL values, fix pipe-separated entries, trim whitespace
    4. Refresh materialized view - Update mv_root_data for API queries

    Each step has automatic retries and can be monitored via Temporal UI.

    Returns workflow ID for tracking execution.
    """
    logger.info(f"[DataCleanup] Starting data cleanup workflow...")

    try:
        # Connect to Temporal with namespace
        temporal_client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)

        # Prepare workflow input
        workflow_input = DataCleanupWorkflowInput(
            include_null_standardization=request.include_null_standardization,
            include_pipe_separation=request.include_pipe_separation,
            include_whitespace_trim=request.include_whitespace_trim,
            refresh_materialized_view=True,
            skip_index_verification=False
        )

        # Start the workflow using workflow name (registered in temporal-worker)
        workflow_id = f"data-cleanup-{int(datetime.utcnow().timestamp() * 1000)}"
        workflow_handle = await temporal_client.start_workflow(
            "DataCleanupWorkflow",  # Workflow name as string (matches class name in worker)
            workflow_input,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
        )

        logger.info(f"[DataCleanup] Workflow started with ID: {workflow_handle.id}")

        return {
            "success": True,
            "message": "Data cleanup workflow started",
            "workflow_id": workflow_handle.id,
            "status": "started",
            "steps": [
                "1. Verifying index health",
                "2. Repairing indexes (if corrupted)",
                "3. Cleaning up data",
                "4. Refreshing materialized view"
            ],
            "instructions": "Monitor workflow progress in Temporal UI or query /workflow-status/<workflow_id>",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"[DataCleanup] Error starting cleanup workflow: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error starting cleanup workflow: {str(e)}"
        )


@router.get("/workflow-status/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """
    Get the status of a data cleanup workflow

    Args:
        workflow_id: The workflow ID returned when starting cleanup

    Returns:
        Workflow status, current step, and execution results
    """
    logger.info(f"[DataCleanup] Getting workflow status for {workflow_id}...")

    try:
        # Connect to Temporal with namespace
        temporal_client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)

        # Get workflow handle
        workflow_handle = temporal_client.get_workflow_handle(workflow_id)

        # Get workflow status
        try:
            result = await workflow_handle.result()
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            # Workflow might still be running
            describe_result = await temporal_client.describe_workflow(workflow_id)
            return {
                "workflow_id": workflow_id,
                "status": "running",
                "execution_status": describe_result.status.name,
                "message": str(e) if "not yet completed" not in str(e) else "Workflow is still executing",
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"[DataCleanup] Error getting workflow status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting workflow status: {str(e)}"
        )


@router.post("/check-index-health")
async def check_index_health(db: Session = Depends(get_db)):
    """
    Check the health of indexes on job_listings_golden table

    Returns information about all indexes and their usage statistics
    """
    logger.info("[DataCleanup] Checking index health...")

    try:
        # Get index statistics
        indexes = db.execute(text("""
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

        index_info = []
        for idx_name, idx_def, blks_read, blks_hit in indexes:
            index_info.append({
                "name": idx_name,
                "blocks_read": blks_read or 0,
                "blocks_hit": blks_hit or 0,
                "definition": idx_def[:100] + "..." if len(idx_def) > 100 else idx_def
            })

        return {
            "healthy": True,
            "message": "All indexes are accessible",
            "indexes": index_info,
            "total_indexes": len(index_info),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        error_str = str(e)
        logger.error(f"[DataCleanup] Error checking index health: {error_str}")

        if "IndexCorrupted" in error_str or "index" in error_str.lower():
            return {
                "healthy": False,
                "message": "Index corruption detected",
                "error": error_str,
                "recovery": "Start data cleanup workflow: POST /api/data-cleanup/cleanup-and-refresh",
                "timestamp": datetime.utcnow().isoformat()
            }

        raise HTTPException(status_code=500, detail=f"Error checking index health: {error_str}")


@router.get("/cleanup-history")
async def get_cleanup_history(db: Session = Depends(get_db)):
    """
    Get history of recent data updates (last 24 hours)

    Shows the timestamp and counts of recently updated records
    """
    logger.info("[DataCleanup] Retrieving cleanup history...")

    try:
        # Get recent updates count by hour
        history = db.execute(text("""
            SELECT
                DATE_TRUNC('hour', updated_at) as hour,
                COUNT(*) as rows_updated,
                MAX(updated_at) as last_update
            FROM job_listings_golden
            WHERE enrichment_status = 'completed'
            AND updated_at > NOW() - INTERVAL '24 hours'
            GROUP BY DATE_TRUNC('hour', updated_at)
            ORDER BY hour DESC
            LIMIT 24
        """)).fetchall()

        return {
            "cleanup_history": [
                {
                    "hour": row[0].isoformat() if row[0] else None,
                    "rows_updated": row[1],
                    "last_update": row[2].isoformat() if row[2] else None
                }
                for row in history
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"[DataCleanup] Error retrieving history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")


@router.get("/salary-stats")
async def get_salary_stats(db: Session = Depends(get_db)):
    """
    Get salary normalization statistics

    Returns counts of salaries by currency and normalization status
    """
    logger.info("[DataCleanup] Getting salary statistics...")

    try:
        # Get count of salaries needing normalization
        total_with_salary = db.execute(text("""
            SELECT COUNT(*)
            FROM job_listings_golden
            WHERE enrichment_status = 'completed'
              AND min_salary_raw IS NOT NULL
        """)).scalar()

        already_normalized = db.execute(text("""
            SELECT COUNT(*)
            FROM job_listings_golden
            WHERE enrichment_status = 'completed'
              AND min_salary_raw IS NOT NULL
              AND currency_conversion_date IS NOT NULL
        """)).scalar()

        needs_normalization = total_with_salary - already_normalized

        # Get breakdown by currency
        currency_breakdown = db.execute(text("""
            SELECT
                COALESCE(currency_raw, 'Unknown') as currency,
                COUNT(*) as count,
                COUNT(CASE WHEN currency_conversion_date IS NOT NULL THEN 1 END) as normalized_count
            FROM job_listings_golden
            WHERE enrichment_status = 'completed'
              AND min_salary_raw IS NOT NULL
            GROUP BY currency_raw
            ORDER BY count DESC
        """)).fetchall()

        # Get average salaries by currency (for normalized ones)
        avg_salaries = db.execute(text("""
            SELECT
                currency_raw,
                ROUND(AVG(min_salary_usd), 2) as avg_min_usd,
                ROUND(AVG(max_salary_usd), 2) as avg_max_usd,
                COUNT(*) as count
            FROM job_listings_golden
            WHERE enrichment_status = 'completed'
              AND currency_conversion_date IS NOT NULL
            GROUP BY currency_raw
            ORDER BY count DESC
        """)).fetchall()

        return {
            "total_with_salary": int(total_with_salary),
            "already_normalized": int(already_normalized),
            "needs_normalization": int(needs_normalization),
            "normalization_percentage": round((already_normalized / total_with_salary * 100) if total_with_salary > 0 else 0, 2),
            "currency_breakdown": [
                {
                    "currency": row[0],
                    "total_count": row[1],
                    "normalized_count": row[2],
                    "needs_normalization": row[1] - row[2]
                }
                for row in currency_breakdown
            ],
            "average_salaries_usd": [
                {
                    "currency": row[0],
                    "avg_min_usd": float(row[1]) if row[1] else 0,
                    "avg_max_usd": float(row[2]) if row[2] else 0,
                    "count": row[3]
                }
                for row in avg_salaries
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"[DataCleanup] Error getting salary stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting salary stats: {str(e)}")


@router.post("/normalize-salaries")
async def normalize_salaries():
    """
    Start a workflow to normalize all salaries to USD

    Converts salaries from various currencies (INR, EUR, GBP, etc.) to USD.
    This endpoint is idempotent - running it multiple times won't keep converting
    already-normalized salaries (tracks via currency_conversion_date field).

    Returns workflow ID for tracking execution.
    """
    logger.info("[SalaryNormalization] Starting salary normalization workflow...")

    try:
        # Connect to Temporal with namespace
        temporal_client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)

        # Start the workflow
        workflow_id = f"salary-normalization-{int(datetime.utcnow().timestamp() * 1000)}"
        workflow_handle = await temporal_client.start_workflow(
            "SalaryNormalizationWorkflow",
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
        )

        logger.info(f"[SalaryNormalization] Workflow started with ID: {workflow_handle.id}")

        return {
            "success": True,
            "message": "Salary normalization workflow started",
            "workflow_id": workflow_handle.id,
            "status": "started",
            "description": "Converting salaries from INR, EUR, GBP, and other currencies to USD",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"[SalaryNormalization] Error starting workflow: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error starting salary normalization workflow: {str(e)}"
        )
