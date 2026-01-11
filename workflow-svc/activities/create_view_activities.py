"""
Temporal activities for creating and deleting custom materialized views.
Handles validation and direct SQL execution for view creation/deletion.
"""
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
    Prepare for creating a custom materialized view.

    Note: We no longer create Alembic migration files since the SQL is executed
    directly. The view metadata is tracked in the custom_materialized_views table.

    Args:
        params: Dictionary with view_id, name, view_name, columns

    Returns:
        Dictionary with revision info (timestamp-based identifier)
    """
    view_id = params["view_id"]
    name = params["name"]
    view_name = params["view_name"]
    columns = params["columns"]

    logger.info(f"[Migration Activity] Preparing view creation for: {view_name}")

    # Generate revision ID (timestamp-based for tracking purposes)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    revision = f"custom_{timestamp}_{name}"

    logger.info(f"[Migration Activity] ✅ Prepared revision: {revision}")

    return {
        "revision": revision,
        "columns": columns
    }


def build_where_clause_from_filters(filters: List[Dict[str, Any]]) -> str:
    """
    Build a WHERE clause from filter conditions.

    Args:
        filters: List of filter condition dictionaries

    Returns:
        SQL WHERE clause string (without 'WHERE' prefix)
    """
    if not filters:
        return ""

    conditions = []
    for i, f in enumerate(filters):
        column = f.get("column", "")
        operator = f.get("operator", "=")
        value = f.get("value")
        logic = f.get("logic")

        # Build condition based on operator
        if operator in ("IS NULL", "IS NOT NULL"):
            condition = f"{column} {operator}"
        elif operator == "BETWEEN":
            if isinstance(value, list) and len(value) == 2:
                condition = f"{column} BETWEEN '{value[0]}' AND '{value[1]}'"
            else:
                continue
        elif operator in ("IN", "NOT IN"):
            if isinstance(value, list):
                values_str = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in value)
                condition = f"{column} {operator} ({values_str})"
            else:
                continue
        elif operator in ("LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE"):
            condition = f"{column} {operator} '{value}'"
        else:
            # Standard comparison operators
            if isinstance(value, str):
                condition = f"{column} {operator} '{value}'"
            elif isinstance(value, bool):
                condition = f"{column} {operator} {str(value).lower()}"
            else:
                condition = f"{column} {operator} {value}"

        conditions.append(condition)

        # Add logic connector if not last filter and logic is specified
        if logic and i < len(filters) - 1:
            conditions.append(logic)

    return " ".join(conditions)


@activity.defn
async def execute_view_migration(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the SQL to create the materialized view.

    Directly executes SQL to create the view - no Alembic migration files needed.

    Args:
        params: Dictionary with view_id, view_name, revision

    Returns:
        Dictionary with execution result
    """
    view_id = params["view_id"]
    view_name = params["view_name"]
    revision = params["revision"]

    logger.info(f"[Execute Activity] Creating materialized view: {view_name}")

    db = SessionLocal()
    try:
        # Get columns and filters from custom_materialized_views table
        result = db.execute(
            text("SELECT columns, filters FROM custom_materialized_views WHERE id = :view_id"),
            {"view_id": view_id}
        ).fetchone()

        if not result:
            raise ValueError(f"View record not found for id: {view_id}")

        # Access by index since raw SQL results may not have named attributes
        columns = result[0]  # columns is first
        filters = result[1] if len(result) > 1 else None  # filters is second

        logger.info(f"[Execute Activity] Columns from DB: {columns}")
        logger.info(f"[Execute Activity] Filters from DB: {filters}")

        # Build and execute CREATE MATERIALIZED VIEW statement
        columns_sql = ", ".join(columns)

        # Build WHERE clause from filters if present
        where_clause = ""
        if filters:
            logger.info(f"[Execute Activity] Building WHERE clause from {len(filters)} filter(s)")
            filter_sql = build_where_clause_from_filters(filters)
            if filter_sql:
                where_clause = f"WHERE {filter_sql}"
                logger.info(f"[Execute Activity] Applying filters: {where_clause}")
            else:
                logger.warning("[Execute Activity] Filter SQL was empty after building")
        else:
            logger.info("[Execute Activity] No filters to apply")

        create_sql = f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT {columns_sql}
            FROM mv_root_data
            {where_clause}
        """

        logger.info(f"[Execute Activity] Executing: CREATE MATERIALIZED VIEW {view_name}")
        db.execute(text(create_sql))

        # Create unique index on id (only if id column is present)
        if "id" in columns:
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
        logger.error(f"[Execute Activity] ❌ View creation failed: {str(e)}")
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
    Prepare for deleting a custom materialized view.

    Note: We no longer create Alembic migration files since the SQL is executed
    directly. The view metadata is tracked in the custom_materialized_views table.

    Args:
        params: Dictionary with view_id, name, view_name

    Returns:
        Dictionary with revision info (timestamp-based identifier)
    """
    view_id = params["view_id"]
    name = params["name"]
    view_name = params["view_name"]

    logger.info(f"[Delete Migration Activity] Preparing deletion for: {view_name}")

    # Generate revision ID (timestamp-based for tracking purposes)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    revision = f"delete_{timestamp}_{name}"

    logger.info(f"[Delete Migration Activity] ✅ Prepared revision: {revision}")

    return {
        "revision": revision
    }


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
