"""
Temporal workflow for deleting custom materialized views.
Handles migration file creation and execution for view deletion.
"""
import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class DeleteCustomViewWorkflow:
    """
    Workflow to delete a custom materialized view.

    Pipeline steps:
    1. Validate view exists and can be deleted
    2. Create migration file for deletion
    3. Execute migration (DROP MATERIALIZED VIEW)
    4. Remove record from tracking table
    """

    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom view deletion workflow.

        Args:
            params: Dictionary containing:
                - view_id: ID of the custom_materialized_views record
                - name: User-friendly name
                - view_name: Actual postgres view name (mv_custom_xxx)

        Returns:
            Summary of workflow execution
        """
        view_id = params["view_id"]
        name = params["name"]
        view_name = params["view_name"]

        workflow.logger.info(
            f"[Delete View Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Delete View Workflow] Deleting view: {name} ({view_name})"
        )
        workflow.logger.info(
            f"[Delete View Workflow] ════════════════════════════════════════"
        )

        try:
            # Step 1: Validate view can be deleted
            workflow.logger.info("[Delete View Workflow] Step 1: Validating deletion...")

            validation_result = await workflow.execute_activity(
                "validate_view_deletion",
                args=[{
                    "view_id": view_id,
                    "name": name,
                    "view_name": view_name,
                }],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=1),
                )
            )

            if not validation_result["valid"]:
                raise ValueError(f"Validation failed: {validation_result['error']}")

            workflow.logger.info(
                f"[Delete View Workflow] ✅ Validation passed"
            )

            # Step 2: Create migration file for deletion
            workflow.logger.info("[Delete View Workflow] Step 2: Creating deletion migration...")

            migration_result = await workflow.execute_activity(
                "create_delete_view_migration",
                args=[{
                    "view_id": view_id,
                    "name": name,
                    "view_name": view_name,
                }],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=1),
                )
            )

            workflow.logger.info(
                f"[Delete View Workflow] ✅ Migration file created: {migration_result['revision']}"
            )

            # Step 3: Execute migration (drop view)
            workflow.logger.info("[Delete View Workflow] Step 3: Executing deletion migration...")

            execution_result = await workflow.execute_activity(
                "execute_delete_view_migration",
                args=[{
                    "view_id": view_id,
                    "view_name": view_name,
                    "revision": migration_result["revision"],
                }],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=2),
                )
            )

            workflow.logger.info(
                f"[Delete View Workflow] ✅ Migration executed, view dropped"
            )

            # Step 4: Remove record from tracking table
            workflow.logger.info("[Delete View Workflow] Step 4: Removing tracking record...")

            await workflow.execute_activity(
                "remove_view_record",
                args=[{
                    "view_id": view_id,
                    "name": name,
                }],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                )
            )

            workflow.logger.info(
                f"[Delete View Workflow] ════════════════════════════════════════"
            )
            workflow.logger.info(
                f"[Delete View Workflow] 🗑️ View deleted successfully!"
            )
            workflow.logger.info(
                f"[Delete View Workflow] ════════════════════════════════════════"
            )

            return {
                "view_id": view_id,
                "name": name,
                "view_name": view_name,
                "status": "deleted",
                "migration_revision": migration_result["revision"],
                "message": f"Successfully deleted view {name}"
            }

        except Exception as e:
            workflow.logger.error(
                f"[Delete View Workflow] ❌ Failed to delete view: {str(e)}"
            )

            # Update status to failed (don't remove the record)
            try:
                await workflow.execute_activity(
                    "update_view_status",
                    args=[{
                        "view_id": view_id,
                        "status": "delete_failed",
                        "error_message": str(e),
                    }],
                    start_to_close_timeout=timedelta(minutes=1),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=1),
                    )
                )
            except Exception:
                pass

            return {
                "view_id": view_id,
                "name": name,
                "view_name": view_name,
                "status": "failed",
                "error": str(e),
                "message": f"Failed to delete view: {str(e)}"
            }
