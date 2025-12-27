"""
Temporal workflow for creating custom materialized views.
Handles validation, migration file creation, and migration execution.
"""
import logging
from datetime import timedelta
from typing import Dict, Any, List
from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class CreateCustomViewWorkflow:
    """
    Workflow to create a custom materialized view.

    Pipeline steps:
    1. Validate view configuration
    2. Create migration file
    3. Execute migration
    4. Update view status (success or failure)
    """

    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom view creation workflow.

        Args:
            params: Dictionary containing:
                - view_id: ID of the custom_materialized_views record
                - name: User-friendly name
                - view_name: Actual postgres view name (mv_custom_xxx)
                - columns: Ordered list of columns
                - display_name: Display name for UI

        Returns:
            Summary of workflow execution
        """
        view_id = params["view_id"]
        name = params["name"]
        view_name = params["view_name"]
        columns = params["columns"]
        display_name = params["display_name"]

        workflow.logger.info(
            f"[Create View Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Create View Workflow] Creating view: {name} ({view_name})"
        )
        workflow.logger.info(
            f"[Create View Workflow] Columns: {columns}"
        )
        workflow.logger.info(
            f"[Create View Workflow] ════════════════════════════════════════"
        )

        try:
            # Step 1: Validate view configuration
            workflow.logger.info("[Create View Workflow] Step 1: Validating configuration...")

            validation_result = await workflow.execute_activity(
                "validate_view_config",
                args=[{
                    "view_id": view_id,
                    "name": name,
                    "view_name": view_name,
                    "columns": columns,
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
                f"[Create View Workflow] ✅ Validation passed"
            )

            # Step 2: Create migration file
            workflow.logger.info("[Create View Workflow] Step 2: Creating migration file...")

            migration_result = await workflow.execute_activity(
                "create_view_migration",
                args=[{
                    "view_id": view_id,
                    "name": name,
                    "view_name": view_name,
                    "columns": columns,
                }],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=1),
                )
            )

            workflow.logger.info(
                f"[Create View Workflow] ✅ Migration file created: {migration_result['revision']}"
            )

            # Step 3: Execute migration
            workflow.logger.info("[Create View Workflow] Step 3: Executing migration...")

            execution_result = await workflow.execute_activity(
                "execute_view_migration",
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
                f"[Create View Workflow] ✅ Migration executed: {execution_result['rows']} rows"
            )

            # Step 4: Update status to completed
            workflow.logger.info("[Create View Workflow] Step 4: Updating status...")

            await workflow.execute_activity(
                "update_view_status",
                args=[{
                    "view_id": view_id,
                    "status": "completed",
                    "row_count": execution_result["rows"],
                    "migration_revision": migration_result["revision"],
                }],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                )
            )

            workflow.logger.info(
                f"[Create View Workflow] ════════════════════════════════════════"
            )
            workflow.logger.info(
                f"[Create View Workflow] 🎉 View created successfully!"
            )
            workflow.logger.info(
                f"[Create View Workflow] ════════════════════════════════════════"
            )

            return {
                "view_id": view_id,
                "name": name,
                "view_name": view_name,
                "status": "completed",
                "rows": execution_result["rows"],
                "migration_revision": migration_result["revision"],
                "message": f"Successfully created view {display_name}"
            }

        except Exception as e:
            workflow.logger.error(
                f"[Create View Workflow] ❌ Failed to create view: {str(e)}"
            )

            # Update status to failed
            try:
                await workflow.execute_activity(
                    "update_view_status",
                    args=[{
                        "view_id": view_id,
                        "status": "failed",
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
                "message": f"Failed to create view: {str(e)}"
            }
