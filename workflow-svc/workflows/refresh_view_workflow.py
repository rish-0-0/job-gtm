"""
Temporal workflow for refreshing materialized views.
Generic workflow that can refresh any materialized view.
"""
import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class RefreshMaterializedViewWorkflow:
    """
    Workflow to refresh a materialized view and notify completion.
    """

    @workflow.run
    async def run(self, view_name: str) -> Dict[str, Any]:
        """
        Execute refresh workflow:
        1. Refresh the materialized view
        2. Publish completion notification to queue

        Args:
            view_name: Name of the materialized view to refresh

        Returns:
            Summary of workflow execution
        """
        workflow.logger.info(
            f"[Refresh View Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Refresh View Workflow] Starting refresh for view: {view_name}"
        )
        workflow.logger.info(
            f"[Refresh View Workflow] ════════════════════════════════════════"
        )

        # Step 1: Refresh the materialized view
        try:
            result = await workflow.execute_activity(
                "refresh_materialized_view",
                args=[view_name],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(seconds=60),
                )
            )

            workflow.logger.info(
                f"[Refresh View Workflow] ✅ View refreshed: {result}"
            )

            # Step 2: Publish completion notification
            await workflow.execute_activity(
                "publish_view_refresh_notification",
                args=[view_name, "completed", result],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                )
            )

            workflow.logger.info(
                f"[Refresh View Workflow] ════════════════════════════════════════"
            )
            workflow.logger.info(
                f"[Refresh View Workflow] 🎉 Workflow completed successfully"
            )
            workflow.logger.info(
                f"[Refresh View Workflow] ════════════════════════════════════════"
            )

            return {
                "view_name": view_name,
                "status": "completed",
                "rows_refreshed": result.get("rows", 0),
                "duration_ms": result.get("duration_ms", 0),
                "message": f"Successfully refreshed {view_name}"
            }

        except Exception as e:
            workflow.logger.error(
                f"[Refresh View Workflow] ❌ Failed to refresh view: {str(e)}"
            )

            # Publish failure notification
            try:
                await workflow.execute_activity(
                    "publish_view_refresh_notification",
                    args=[view_name, "failed", {"error": str(e)}],
                    start_to_close_timeout=timedelta(minutes=1),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=1),
                    )
                )
            except Exception:
                pass

            return {
                "view_name": view_name,
                "status": "failed",
                "error": str(e),
                "message": f"Failed to refresh {view_name}: {str(e)}"
            }
