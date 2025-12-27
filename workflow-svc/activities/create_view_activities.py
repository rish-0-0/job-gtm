"""
Temporal activities for creating and deleting custom materialized views.
Handles validation, migration file creation, and execution.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, List
from temporalio import activity
from sqlalchemy import text

from database import SessionLocal

logger = logging.getLogger(__name__)

# Valid columns that can be selected (from mv_root_data)
VALID_COLUMNS = [
    "id",
    "company_title",
    "job_role",
    "job_location_normalized",
    "employment_type_normalized",
    "min_salary_usd",
    "max_salary_usd",
    "seniority_level_normalized",
    "is_remote",
    "location_city",
    "location_country",
    "company_industry",
    "company_size",
    "primary_role",
    "role_category",
    "scraper_source",
    "enrichment_status",
    "created_at",
]

# Path to API alembic versions directory
# Note: This path is relative to the workflow-svc container
# In docker-compose, we'll mount the api/alembic directory
API_ALEMBIC_VERSIONS_PATH = os.getenv(
    "API_ALEMBIC_VERSIONS_PATH",
    "/app/api_alembic/versions"
)


@activity.defn
async def validate_view_config(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the view configuration.

    Args:
        params: Dictionary with view_id, name, view_name, columns

    Returns:
        Dictionary with validation result
    """
    view_id = params["view_id"]
    name = params["name"]
    view_name = params["view_name"]
    columns = params["columns"]

    logger.info(f"[Validate Activity] Validating view config for: {name}")

    # Validate columns
    invalid_cols = [col for col in columns if col not in VALID_COLUMNS]
    if invalid_cols:
        return {
            "valid": False,
            "error": f"Invalid columns: {invalid_cols}"
        }

    # Check for duplicates
    if len(columns) != len(set(columns)):
        return {
            "valid": False,
            "error": "Duplicate columns detected"
        }

    # Ensure id column is present
    if "id" not in columns:
        return {
            "valid": False,
            "error": "'id' column is required"
        }

    db = SessionLocal()
    try:
        # Check if view already exists in postgres
        view_exists = db.execute(
            text("SELECT COUNT(*) FROM pg_matviews WHERE matviewname = :view_name"),
            {"view_name": view_name}
        ).scalar()

        if view_exists > 0:
            return {
                "valid": False,
                "error": f"Materialized view '{view_name}' already exists"
            }

        # Check if source view (mv_root_data) exists
        source_exists = db.execute(
            text("SELECT COUNT(*) FROM pg_matviews WHERE matviewname = 'mv_root_data'")
        ).scalar()

        if source_exists == 0:
            return {
                "valid": False,
                "error": "Source view 'mv_root_data' does not exist"
            }

        logger.info(f"[Validate Activity] ✅ Validation passed for: {name}")
        return {
            "valid": True,
            "columns": columns
        }

    except Exception as e:
        logger.error(f"[Validate Activity] ❌ Validation error: {str(e)}")
        return {
            "valid": False,
            "error": str(e)
        }
    finally:
        db.close()


@activity.defn
async def create_view_migration(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an Alembic migration file for the custom view.

    Args:
        params: Dictionary with view_id, name, view_name, columns

    Returns:
        Dictionary with migration file info
    """
    view_id = params["view_id"]
    name = params["name"]
    view_name = params["view_name"]
    columns = params["columns"]

    logger.info(f"[Migration Activity] Creating migration for: {view_name}")

    # Generate revision ID (timestamp-based for uniqueness)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    revision = f"custom_{timestamp}_{name}"

    # Build column list for SQL
    columns_sql = ",\n            ".join(columns)

    # Generate migration file content
    migration_content = f'''"""Create custom materialized view: {name}

Revision ID: {revision}
Revises: 002
Create Date: {datetime.now().isoformat()}

Auto-generated migration for custom view.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "{revision}"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW {view_name} AS
        SELECT
            {columns_sql}
        FROM mv_root_data
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_{view_name}_id ON {view_name}(id)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS {view_name}")
'''

    # Write migration file
    migration_filename = f"{revision}.py"
    migration_path = os.path.join(API_ALEMBIC_VERSIONS_PATH, migration_filename)

    try:
        # Ensure directory exists
        os.makedirs(API_ALEMBIC_VERSIONS_PATH, exist_ok=True)

        with open(migration_path, "w") as f:
            f.write(migration_content)

        logger.info(f"[Migration Activity] ✅ Created migration file: {migration_filename}")

        return {
            "revision": revision,
            "filename": migration_filename,
            "path": migration_path,
            "columns": columns
        }

    except Exception as e:
        logger.error(f"[Migration Activity] ❌ Failed to create migration: {str(e)}")
        raise


@activity.defn
async def execute_view_migration(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the migration to create the materialized view.

    Instead of running alembic upgrade (which requires alembic context),
    we directly execute the SQL to create the view.

    Args:
        params: Dictionary with view_id, view_name, revision

    Returns:
        Dictionary with execution result
    """
    view_id = params["view_id"]
    view_name = params["view_name"]
    revision = params["revision"]

    logger.info(f"[Execute Activity] Executing migration for: {view_name}")

    db = SessionLocal()
    try:
        # Read the migration file to get the SQL
        migration_path = os.path.join(API_ALEMBIC_VERSIONS_PATH, f"{revision}.py")

        if not os.path.exists(migration_path):
            raise FileNotFoundError(f"Migration file not found: {migration_path}")

        # Parse columns from custom_materialized_views table
        result = db.execute(
            text("SELECT columns FROM custom_materialized_views WHERE id = :view_id"),
            {"view_id": view_id}
        ).fetchone()

        if not result:
            raise ValueError(f"View record not found for id: {view_id}")

        columns = result.columns

        # Build and execute CREATE MATERIALIZED VIEW statement
        columns_sql = ", ".join(columns)

        create_sql = f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT {columns_sql}
            FROM mv_root_data
        """

        logger.info(f"[Execute Activity] Executing: CREATE MATERIALIZED VIEW {view_name}")
        db.execute(text(create_sql))

        # Create unique index on id
        index_sql = f"CREATE UNIQUE INDEX idx_{view_name}_id ON {view_name}(id)"
        logger.info(f"[Execute Activity] Creating index: idx_{view_name}_id")
        db.execute(text(index_sql))

        db.commit()

        # Get row count
        count_result = db.execute(text(f"SELECT COUNT(*) FROM {view_name}"))
        row_count = count_result.scalar()

        logger.info(f"[Execute Activity] ✅ View created with {row_count} rows")

        return {
            "view_name": view_name,
            "rows": row_count,
            "revision": revision,
            "status": "completed"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Execute Activity] ❌ Migration execution failed: {str(e)}")
        raise
    finally:
        db.close()


@activity.defn
async def update_view_status(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the status of a custom view record.

    Args:
        params: Dictionary with view_id, status, and optional fields

    Returns:
        Dictionary with update result
    """
    view_id = params["view_id"]
    status = params["status"]
    row_count = params.get("row_count")
    error_message = params.get("error_message")
    migration_revision = params.get("migration_revision")

    logger.info(f"[Update Status Activity] Updating view {view_id} to status: {status}")

    db = SessionLocal()
    try:
        update_fields = ["status = :status", "updated_at = NOW()"]
        update_params = {"view_id": view_id, "status": status}

        if row_count is not None:
            update_fields.append("row_count = :row_count")
            update_fields.append("last_refreshed_at = NOW()")
            update_params["row_count"] = row_count

        if error_message is not None:
            update_fields.append("error_message = :error_message")
            update_params["error_message"] = error_message

        if migration_revision is not None:
            update_fields.append("migration_revision = :migration_revision")
            update_params["migration_revision"] = migration_revision

        update_sql = f"""
            UPDATE custom_materialized_views
            SET {', '.join(update_fields)}
            WHERE id = :view_id
        """

        db.execute(text(update_sql), update_params)
        db.commit()

        logger.info(f"[Update Status Activity] ✅ Status updated to: {status}")

        return {
            "view_id": view_id,
            "status": status,
            "updated": True
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Update Status Activity] ❌ Failed to update status: {str(e)}")
        raise
    finally:
        db.close()


# ============================================================================
# DELETE VIEW ACTIVITIES
# ============================================================================


@activity.defn
async def validate_view_deletion(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that a view can be deleted.

    Args:
        params: Dictionary with view_id, name, view_name

    Returns:
        Dictionary with validation result
    """
    view_id = params["view_id"]
    name = params["name"]
    view_name = params["view_name"]

    logger.info(f"[Validate Deletion Activity] Validating deletion for: {name}")

    db = SessionLocal()
    try:
        # Check if record exists in tracking table
        record = db.execute(
            text("SELECT id, status FROM custom_materialized_views WHERE id = :view_id"),
            {"view_id": view_id}
        ).fetchone()

        if not record:
            return {
                "valid": False,
                "error": f"View record not found for id: {view_id}"
            }

        # Check if view exists in postgres
        view_exists = db.execute(
            text("SELECT COUNT(*) FROM pg_matviews WHERE matviewname = :view_name"),
            {"view_name": view_name}
        ).scalar()

        # It's okay if view doesn't exist in postgres - we still want to clean up the record
        if view_exists == 0:
            logger.warning(f"[Validate Deletion Activity] View {view_name} not found in postgres, will clean up record")

        logger.info(f"[Validate Deletion Activity] ✅ Validation passed for: {name}")
        return {
            "valid": True,
            "view_exists_in_postgres": view_exists > 0
        }

    except Exception as e:
        logger.error(f"[Validate Deletion Activity] ❌ Validation error: {str(e)}")
        return {
            "valid": False,
            "error": str(e)
        }
    finally:
        db.close()


@activity.defn
async def create_delete_view_migration(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an Alembic migration file for dropping the custom view.

    Args:
        params: Dictionary with view_id, name, view_name

    Returns:
        Dictionary with migration file info
    """
    view_id = params["view_id"]
    name = params["name"]
    view_name = params["view_name"]

    logger.info(f"[Delete Migration Activity] Creating deletion migration for: {view_name}")

    # Generate revision ID (timestamp-based for uniqueness)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    revision = f"delete_{timestamp}_{name}"

    # Generate migration file content
    migration_content = f'''"""Delete custom materialized view: {name}

Revision ID: {revision}
Revises: 002
Create Date: {datetime.now().isoformat()}

Auto-generated migration for deleting custom view.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "{revision}"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the index first
    op.execute("DROP INDEX IF EXISTS idx_{view_name}_id")
    # Drop the materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS {view_name}")


def downgrade() -> None:
    # Note: downgrade would require knowing the original columns
    # which is not stored in this migration. Manual intervention needed.
    pass
'''

    # Write migration file
    migration_filename = f"{revision}.py"
    migration_path = os.path.join(API_ALEMBIC_VERSIONS_PATH, migration_filename)

    try:
        # Ensure directory exists
        os.makedirs(API_ALEMBIC_VERSIONS_PATH, exist_ok=True)

        with open(migration_path, "w") as f:
            f.write(migration_content)

        logger.info(f"[Delete Migration Activity] ✅ Created migration file: {migration_filename}")

        return {
            "revision": revision,
            "filename": migration_filename,
            "path": migration_path
        }

    except Exception as e:
        logger.error(f"[Delete Migration Activity] ❌ Failed to create migration: {str(e)}")
        raise


@activity.defn
async def execute_delete_view_migration(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the migration to drop the materialized view.

    Args:
        params: Dictionary with view_id, view_name, revision

    Returns:
        Dictionary with execution result
    """
    view_id = params["view_id"]
    view_name = params["view_name"]
    revision = params["revision"]

    logger.info(f"[Execute Delete Activity] Executing deletion migration for: {view_name}")

    db = SessionLocal()
    try:
        # Drop the index first (if exists)
        index_name = f"idx_{view_name}_id"
        logger.info(f"[Execute Delete Activity] Dropping index: {index_name}")
        db.execute(text(f"DROP INDEX IF EXISTS {index_name}"))

        # Drop the materialized view
        logger.info(f"[Execute Delete Activity] Dropping view: {view_name}")
        db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))

        db.commit()

        logger.info(f"[Execute Delete Activity] ✅ View dropped: {view_name}")

        return {
            "view_name": view_name,
            "revision": revision,
            "status": "deleted"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Execute Delete Activity] ❌ Deletion failed: {str(e)}")
        raise
    finally:
        db.close()


@activity.defn
async def remove_view_record(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove the view record from the tracking table.

    Args:
        params: Dictionary with view_id, name

    Returns:
        Dictionary with removal result
    """
    view_id = params["view_id"]
    name = params["name"]

    logger.info(f"[Remove Record Activity] Removing record for view: {name}")

    db = SessionLocal()
    try:
        db.execute(
            text("DELETE FROM custom_materialized_views WHERE id = :view_id"),
            {"view_id": view_id}
        )
        db.commit()

        logger.info(f"[Remove Record Activity] ✅ Record removed for: {name}")

        return {
            "view_id": view_id,
            "name": name,
            "removed": True
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Remove Record Activity] ❌ Failed to remove record: {str(e)}")
        raise
    finally:
        db.close()
