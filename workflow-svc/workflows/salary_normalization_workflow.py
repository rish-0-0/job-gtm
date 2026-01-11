"""
Salary Normalization Workflow for Temporal
Converts salaries from various currencies to USD
"""
import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class SalaryNormalizationWorkflow:
    """
    Workflow for normalizing salaries to USD

    This workflow converts salaries from various currencies (INR, EUR, GBP, etc.) to USD.
    It's idempotent - only processes rows that haven't been normalized yet (currency_conversion_date IS NULL).
    Running this workflow multiple times won't keep converting already-normalized salaries.

    Steps:
    1. Normalize salaries - Detect currency, convert to USD, update records
    2. Refresh materialized view - Update cached view with new USD salaries
    """

    @workflow.run
    async def run(self) -> dict:
        """
        Main workflow execution

        Returns:
            Workflow execution results
        """
        logger.info("[SalaryNormalizationWorkflow] Starting salary normalization workflow...")

        # ====================================================================
        # STEP 1: Normalize Salaries to USD
        # ====================================================================
        try:
            logger.info("[SalaryNormalizationWorkflow] STEP 1: Normalizing salaries to USD...")

            normalization_result = await workflow.execute_activity(
                "normalize_salaries_to_usd",
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2,
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )

            logger.info(f"[SalaryNormalizationWorkflow] Normalization result: {normalization_result}")

            if not normalization_result.get("success"):
                raise Exception(f"Salary normalization failed: {normalization_result.get('message')}")

        except Exception as e:
            error_msg = f"Salary normalization failed: {str(e)}"
            logger.error(f"[SalaryNormalizationWorkflow] {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "workflow_status": "failed"
            }

        # ====================================================================
        # STEP 2: Refresh Materialized View
        # ====================================================================
        try:
            logger.info("[SalaryNormalizationWorkflow] STEP 2: Refreshing materialized view...")

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

            logger.info(f"[SalaryNormalizationWorkflow] View refresh result: {refresh_result}")

        except Exception as e:
            # Don't fail the workflow if view refresh fails - normalization was successful
            error_msg = f"Materialized view refresh failed: {str(e)}"
            logger.warning(f"[SalaryNormalizationWorkflow] {error_msg}")
            logger.warning("[SalaryNormalizationWorkflow] Normalization succeeded but view refresh failed")

        # ====================================================================
        # WORKFLOW COMPLETED
        # ====================================================================
        logger.info("[SalaryNormalizationWorkflow] Salary normalization workflow completed successfully")

        return {
            "success": True,
            "message": "Salary normalization completed successfully",
            "rows_updated": normalization_result.get("rows_updated", 0),
            "currency_stats": normalization_result.get("currency_stats", {}),
            "workflow_status": "completed"
        }
