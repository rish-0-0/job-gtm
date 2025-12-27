"""
Custom materialized views management endpoints.
Allows users to create views with selected columns from mv_root_data.
"""
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from temporalio.client import Client
from temporalio.service import RPCError

from app.database import get_db
from app.config import TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE

router = APIRouter()

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

# Reserved view names (system views)
RESERVED_VIEW_NAMES = [
    "root_data",
    "mv_root_data",
]


class CreateViewRequest(BaseModel):
    """Request body for creating a custom materialized view."""
    name: str  # User-friendly name (e.g., "my_sales_jobs")
    display_name: str  # Display name for UI (e.g., "My Sales Jobs")
    description: Optional[str] = None
    columns: List[str]  # Ordered list of columns to include

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        # Must be lowercase, alphanumeric with underscores, 3-50 chars
        if not re.match(r"^[a-z][a-z0-9_]{2,49}$", v):
            raise ValueError(
                "Name must be 3-50 characters, start with a letter, "
                "and contain only lowercase letters, numbers, and underscores"
            )
        if v in RESERVED_VIEW_NAMES:
            raise ValueError(f"Name '{v}' is reserved and cannot be used")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 100:
            raise ValueError("Display name must be 3-100 characters")
        return v.strip()

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one column must be specified")
        if len(v) > len(VALID_COLUMNS):
            raise ValueError(f"Too many columns specified (max {len(VALID_COLUMNS)})")

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate columns are not allowed")

        # Validate each column
        invalid_cols = [col for col in v if col not in VALID_COLUMNS]
        if invalid_cols:
            raise ValueError(
                f"Invalid columns: {invalid_cols}. Valid columns are: {VALID_COLUMNS}"
            )

        # Ensure 'id' is always first if present (or add it)
        if "id" in v and v[0] != "id":
            v.remove("id")
            v.insert(0, "id")
        elif "id" not in v:
            v.insert(0, "id")

        return v


class CreateViewResponse(BaseModel):
    """Response for create view request."""
    id: int
    name: str
    display_name: str
    view_name: str
    columns: List[str]
    status: str
    workflow_id: Optional[str] = None
    message: str


class ViewStatusResponse(BaseModel):
    """Response for view status check."""
    id: int
    name: str
    display_name: str
    view_name: str
    columns: List[str]
    status: str
    error_message: Optional[str] = None
    workflow_id: Optional[str] = None
    row_count: Optional[int] = None
    last_refreshed_at: Optional[str] = None


class ListViewsResponse(BaseModel):
    """Response for listing all custom views."""
    views: List[ViewStatusResponse]


class AvailableColumnsResponse(BaseModel):
    """Response for available columns."""
    columns: List[str]


class DeleteViewResponse(BaseModel):
    """Response for delete view request."""
    name: str
    view_name: str
    status: str
    workflow_id: Optional[str] = None
    message: str


async def get_temporal_client() -> Client:
    """Get a Temporal client connection."""
    try:
        return await Client.connect(TEMPORAL_ADDRESS)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Temporal: {str(e)}"
        )


@router.get("/columns", response_model=AvailableColumnsResponse)
async def get_available_columns():
    """Get list of columns available for custom views."""
    return {"columns": VALID_COLUMNS}


@router.get("", response_model=ListViewsResponse)
async def list_custom_views(db: Session = Depends(get_db)):
    """List all custom materialized views."""
    result = db.execute(
        text("""
            SELECT id, name, display_name, view_name, columns, status,
                   error_message, workflow_id, row_count, last_refreshed_at
            FROM custom_materialized_views
            ORDER BY created_at DESC
        """)
    )
    rows = result.fetchall()

    views = []
    for row in rows:
        views.append(ViewStatusResponse(
            id=row.id,
            name=row.name,
            display_name=row.display_name,
            view_name=row.view_name,
            columns=row.columns,
            status=row.status,
            error_message=row.error_message,
            workflow_id=row.workflow_id,
            row_count=row.row_count,
            last_refreshed_at=str(row.last_refreshed_at) if row.last_refreshed_at else None,
        ))

    return {"views": views}


@router.post("", response_model=CreateViewResponse)
async def create_custom_view(
    request: CreateViewRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new custom materialized view.

    This endpoint:
    1. Validates the request (columns, name)
    2. Creates a record in custom_materialized_views table
    3. Starts a Temporal workflow to create the migration and execute it
    """
    # Generate the actual view name (prefixed with mv_custom_)
    view_name = f"mv_custom_{request.name}"

    # Check if name already exists
    existing = db.execute(
        text("SELECT id FROM custom_materialized_views WHERE name = :name OR view_name = :view_name"),
        {"name": request.name, "view_name": view_name}
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A view with name '{request.name}' already exists"
        )

    # Check if view already exists in postgres
    view_exists = db.execute(
        text("SELECT COUNT(*) FROM pg_matviews WHERE matviewname = :view_name"),
        {"view_name": view_name}
    ).scalar()

    if view_exists > 0:
        raise HTTPException(
            status_code=400,
            detail=f"A materialized view '{view_name}' already exists in the database"
        )

    # Insert record with pending status
    result = db.execute(
        text("""
            INSERT INTO custom_materialized_views
            (name, display_name, description, columns, view_name, status)
            VALUES (:name, :display_name, :description, :columns, :view_name, 'pending')
            RETURNING id
        """),
        {
            "name": request.name,
            "display_name": request.display_name,
            "description": request.description,
            "columns": request.columns,
            "view_name": view_name,
        }
    )
    view_id = result.fetchone()[0]
    db.commit()

    # Start Temporal workflow
    try:
        client = await get_temporal_client()
        workflow_id = f"create-custom-view-{request.name}"

        # Check if workflow is already running
        try:
            handle = client.get_workflow_handle(workflow_id)
            description = await handle.describe()
            if description.status.name == "RUNNING":
                raise HTTPException(
                    status_code=400,
                    detail=f"A workflow for this view is already running"
                )
        except RPCError:
            # Workflow doesn't exist, which is fine
            pass

        # Start the workflow
        handle = await client.start_workflow(
            "CreateCustomViewWorkflow",
            {
                "view_id": view_id,
                "name": request.name,
                "view_name": view_name,
                "columns": request.columns,
                "display_name": request.display_name,
            },
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
        )

        # Update record with workflow ID
        db.execute(
            text("""
                UPDATE custom_materialized_views
                SET workflow_id = :workflow_id, status = 'creating'
                WHERE id = :view_id
            """),
            {"workflow_id": workflow_id, "view_id": view_id}
        )
        db.commit()

        return CreateViewResponse(
            id=view_id,
            name=request.name,
            display_name=request.display_name,
            view_name=view_name,
            columns=request.columns,
            status="creating",
            workflow_id=workflow_id,
            message=f"View creation workflow started. View will be available shortly."
        )

    except HTTPException:
        raise
    except Exception as e:
        # Update status to failed
        db.execute(
            text("""
                UPDATE custom_materialized_views
                SET status = 'failed', error_message = :error
                WHERE id = :view_id
            """),
            {"error": str(e), "view_id": view_id}
        )
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to start view creation workflow: {str(e)}"
        )


@router.get("/{name}", response_model=ViewStatusResponse)
async def get_custom_view(name: str, db: Session = Depends(get_db)):
    """Get status and details of a custom view."""
    result = db.execute(
        text("""
            SELECT id, name, display_name, view_name, columns, status,
                   error_message, workflow_id, row_count, last_refreshed_at
            FROM custom_materialized_views
            WHERE name = :name
        """),
        {"name": name}
    ).fetchone()

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"View '{name}' not found"
        )

    return ViewStatusResponse(
        id=result.id,
        name=result.name,
        display_name=result.display_name,
        view_name=result.view_name,
        columns=result.columns,
        status=result.status,
        error_message=result.error_message,
        workflow_id=result.workflow_id,
        row_count=result.row_count,
        last_refreshed_at=str(result.last_refreshed_at) if result.last_refreshed_at else None,
    )


@router.delete("/{name}", response_model=DeleteViewResponse)
async def delete_custom_view(name: str, db: Session = Depends(get_db)):
    """
    Delete a custom materialized view.

    This endpoint:
    1. Finds the view record
    2. Updates status to 'deleting'
    3. Starts a Temporal workflow to create deletion migration and execute it
    4. The workflow will remove the record after successful deletion
    """
    result = db.execute(
        text("SELECT id, view_name, status FROM custom_materialized_views WHERE name = :name"),
        {"name": name}
    ).fetchone()

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"View '{name}' not found"
        )

    view_id = result.id
    view_name = result.view_name
    current_status = result.status

    # Check if already being deleted
    if current_status == "deleting":
        raise HTTPException(
            status_code=400,
            detail=f"View '{name}' is already being deleted"
        )

    # Start Temporal workflow for deletion
    try:
        client = await get_temporal_client()
        workflow_id = f"delete-custom-view-{name}"

        # Check if workflow is already running
        try:
            handle = client.get_workflow_handle(workflow_id)
            description = await handle.describe()
            if description.status.name == "RUNNING":
                raise HTTPException(
                    status_code=400,
                    detail=f"A deletion workflow for this view is already running"
                )
        except RPCError:
            # Workflow doesn't exist, which is fine
            pass

        # Update status to deleting
        db.execute(
            text("""
                UPDATE custom_materialized_views
                SET status = 'deleting', workflow_id = :workflow_id
                WHERE id = :view_id
            """),
            {"workflow_id": workflow_id, "view_id": view_id}
        )
        db.commit()

        # Start the workflow
        await client.start_workflow(
            "DeleteCustomViewWorkflow",
            {
                "view_id": view_id,
                "name": name,
                "view_name": view_name,
            },
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
        )

        return DeleteViewResponse(
            name=name,
            view_name=view_name,
            status="deleting",
            workflow_id=workflow_id,
            message=f"View deletion workflow started. View will be removed shortly."
        )

    except HTTPException:
        raise
    except Exception as e:
        # Revert status on failure
        db.execute(
            text("""
                UPDATE custom_materialized_views
                SET status = :old_status, error_message = :error
                WHERE id = :view_id
            """),
            {"old_status": current_status, "error": str(e), "view_id": view_id}
        )
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to start view deletion workflow: {str(e)}"
        )
