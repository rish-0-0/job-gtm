"""
Data Cleanup Workflow for Temporal
Orchestrates index verification and data cleanup with automatic retries and error recovery
"""
import logging
from datetime import timedelta
from typing import Optional
from dataclasses import dataclass

from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@dataclass
class DataCleanupWorkflowInput:
    """Input parameters for data cleanup workflow"""
    include_null_standardization: bool = True
    include_pipe_separation: bool = True
    include_whitespace_trim: bool = True
    refresh_materialized_view: bool = True
    skip_index_verification: bool = False


@dataclass
class WorkflowStepResult:
    """Result of a workflow step"""
    step: str
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


@workflow.defn
class DataCleanupWorkflow:
    """
    Workflow for cleaning up golden job listings data

    Steps:
    1. Verify index health - Check if indexes are corrupted
    2. Repair indexes (if needed) - Rebuild corrupted indexes
    3. Clean up data - Standardize values, fix pipe-separated entries, trim whitespace
    4. Refresh materialized view - Update cached view for API queries

    The workflow is resilient:
    - Each step has retries configured
    - Failures are captured and reported
    - Can be paused, resumed, and restarted
    - Provides detailed execution history via Temporal
    """

    @workflow.run
    async def run(self, input_params: DataCleanupWorkflowInput) -> dict:
        """
        Main workflow execution

        Args:
            input_params: Cleanup configuration

        Returns:
            Workflow execution results with all steps and their outcomes
        """
        logger.info("[DataCleanupWorkflow] Starting data cleanup workflow...")

        steps_results = []
        index_repair_needed = False

        # ====================================================================
        # STEP 1: Verify Index Health
        # ====================================================================
        try:
            logger.info("[DataCleanupWorkflow] STEP 1: Verifying index health...")

            index_health = await workflow.execute_activity(
                "verify_index_health",
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2,
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )

            steps_results.append(WorkflowStepResult(
                step="verify_index_health",
                success=True,
                message="Index health verification completed",
                data=index_health
            ))

            logger.info(f"[DataCleanupWorkflow] Index health: {index_health}")

            # Check if indexes are corrupted
            if index_health.get("corrupted"):
                index_repair_needed = True
                logger.warning("[DataCleanupWorkflow] Index corruption detected. "
                             "Will repair before cleanup.")

        except Exception as e:
            error_msg = f"Index verification failed: {str(e)}"
            logger.error(f"[DataCleanupWorkflow] {error_msg}")
            steps_results.append(WorkflowStepResult(
                step="verify_index_health",
                success=False,
                message="Index health verification failed",
                error=error_msg
            ))
            raise

        # ====================================================================
        # STEP 2: Repair Indexes (if needed)
        # ====================================================================
        if index_repair_needed and not input_params.skip_index_verification:
            try:
                logger.info("[DataCleanupWorkflow] STEP 2: Repairing indexes...")

                repair_result = await workflow.execute_activity(
                    "repair_indexes",
                    start_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=5),
                        backoff_coefficient=2,
                        maximum_interval=timedelta(minutes=1),
                        maximum_attempts=2
                    )
                )

                if repair_result.get("success"):
                    steps_results.append(WorkflowStepResult(
                        step="repair_indexes",
                        success=True,
                        message="Index repair completed successfully",
                        data=repair_result
                    ))
                    logger.info(f"[DataCleanupWorkflow] Index repair result: {repair_result}")
                else:
                    error_msg = repair_result.get("message", "Index repair failed")
                    steps_results.append(WorkflowStepResult(
                        step="repair_indexes",
                        success=False,
                        message=error_msg,
                        error=repair_result.get("error")
                    ))
                    raise Exception(error_msg)

            except Exception as e:
                error_msg = f"Index repair failed: {str(e)}"
                logger.error(f"[DataCleanupWorkflow] {error_msg}")
                steps_results.append(WorkflowStepResult(
                    step="repair_indexes",
                    success=False,
                    message="Index repair failed",
                    error=error_msg
                ))
                raise

        # ====================================================================
        # STEP 3: Clean Up Data
        # ====================================================================
        try:
            logger.info("[DataCleanupWorkflow] STEP 3: Cleaning up data...")

            cleanup_result = await workflow.execute_activity(
                "cleanup_job_listings_data",
                args=[
                    input_params.include_null_standardization,
                    input_params.include_pipe_separation,
                    input_params.include_whitespace_trim
                ],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2,
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=2
                )
            )

            steps_results.append(WorkflowStepResult(
                step="cleanup_data",
                success=True,
                message="Data cleanup completed successfully",
                data=cleanup_result
            ))

            logger.info(f"[DataCleanupWorkflow] Data cleanup result: {cleanup_result}")

        except Exception as e:
            error_msg = f"Data cleanup failed: {str(e)}"
            logger.error(f"[DataCleanupWorkflow] {error_msg}")
            steps_results.append(WorkflowStepResult(
                step="cleanup_data",
                success=False,
                message="Data cleanup failed",
                error=error_msg
            ))
            raise

        # ====================================================================
        # STEP 4: Refresh Materialized View
        # ====================================================================
        if input_params.refresh_materialized_view:
            try:
                logger.info("[DataCleanupWorkflow] STEP 4: Refreshing materialized view...")

                refresh_result = await workflow.execute_activity(
                    "data_cleanup_refresh_view",
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2,
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=3
                    )
                )

                steps_results.append(WorkflowStepResult(
                    step="refresh_materialized_view",
                    success=True,
                    message="Materialized view refreshed successfully",
                    data=refresh_result
                ))

                logger.info(f"[DataCleanupWorkflow] View refresh result: {refresh_result}")

            except Exception as e:
                error_msg = f"Materialized view refresh failed: {str(e)}"
                logger.error(f"[DataCleanupWorkflow] {error_msg}")
                steps_results.append(WorkflowStepResult(
                    step="refresh_materialized_view",
                    success=False,
                    message="Materialized view refresh failed",
                    error=error_msg
                ))
                # Don't raise here - cleanup was successful, view refresh is secondary
                logger.warning("[DataCleanupWorkflow] View refresh failed but cleanup succeeded")

        # ====================================================================
        # WORKFLOW COMPLETED
        # ====================================================================
        logger.info("[DataCleanupWorkflow] Data cleanup workflow completed successfully")

        return {
            "success": True,
            "message": "Data cleanup workflow completed successfully",
            "steps": [
                {
                    "step": r.step,
                    "success": r.success,
                    "message": r.message,
                    "data": r.data,
                    "error": r.error
                }
                for r in steps_results
            ],
            "workflow_status": "completed"
        }
