"""
Workflow management endpoints.
Triggers Temporal workflows and checks their status.
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from temporalio.client import Client
from temporalio.service import RPCError

from app.config import TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE
from app.database import get_db

router = APIRouter()

# System materialized views that can be refreshed
SYSTEM_VIEWS = [
    "mv_root_data",
    "mv_jobs_by_seniority",
    "mv_jobs_by_location",
    "mv_jobs_by_company",
    "mv_jobs_by_role",
    "mv_jobs_by_source",
    "mv_salary_distribution",
]


def get_allowed_views(db: Session) -> List[str]:
    """Get list of allowed views including custom views from database."""
    try:
        result = db.execute(
            text("SELECT view_name FROM custom_materialized_views WHERE status = 'completed'")
        )
        custom_views = [row[0] for row in result.fetchall()]
        return SYSTEM_VIEWS + custom_views
    except Exception:
        # Table might not exist yet
        return SYSTEM_VIEWS


class RefreshViewRequest(BaseModel):
    view_name: str


class RefreshViewResponse(BaseModel):
    workflow_id: str
    view_name: str
    status: str
    message: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    result: Optional[dict] = None


class AvailableViewsResponse(BaseModel):
    views: List[str]


async def get_temporal_client() -> Client:
    """Get a Temporal client connection."""
    try:
        return await Client.connect(TEMPORAL_ADDRESS)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Temporal: {str(e)}"
        )


@router.get("/views/available", response_model=AvailableViewsResponse)
async def get_available_views(db: Session = Depends(get_db)):
    """Get list of materialized views that can be refreshed."""
    allowed_views = get_allowed_views(db)
    return {"views": allowed_views}


@router.post("/views/refresh", response_model=RefreshViewResponse)
async def refresh_materialized_view(
    request: RefreshViewRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger a workflow to refresh a materialized view.
    Checks if a refresh is already running before starting a new one.
    """
    view_name = request.view_name
    allowed_views = get_allowed_views(db)

    # Validate view name
    if view_name not in allowed_views:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view name: {view_name}. Allowed views: {allowed_views}"
        )

    client = await get_temporal_client()

    # Use a deterministic workflow ID based on view name to prevent duplicates
    workflow_id = f"refresh-view-{view_name}"

    try:
        # Check if workflow is already running
        try:
            handle = client.get_workflow_handle(workflow_id)
            description = await handle.describe()
            status = description.status.name

            if status == "RUNNING":
                return RefreshViewResponse(
                    workflow_id=workflow_id,
                    view_name=view_name,
                    status="already_running",
                    message=f"Refresh for {view_name} is already in progress"
                )
        except RPCError:
            # Workflow doesn't exist, which is fine
            pass

        # Start the workflow
        handle = await client.start_workflow(
            "RefreshMaterializedViewWorkflow",
            view_name,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
        )

        return RefreshViewResponse(
            workflow_id=workflow_id,
            view_name=view_name,
            status="started",
            message=f"Refresh workflow started for {view_name}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start refresh workflow: {str(e)}"
        )


@router.get("/views/refresh/{view_name}/status", response_model=WorkflowStatusResponse)
async def get_refresh_status(view_name: str, db: Session = Depends(get_db)):
    """
    Get the status of a view refresh workflow.
    """
    allowed_views = get_allowed_views(db)
    if view_name not in allowed_views:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view name: {view_name}"
        )

    client = await get_temporal_client()
    workflow_id = f"refresh-view-{view_name}"

    try:
        handle = client.get_workflow_handle(workflow_id)
        description = await handle.describe()
        status = description.status.name

        result = None
        if status == "COMPLETED":
            try:
                result = await handle.result()
            except Exception:
                pass

        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=status.lower(),
            result=result
        )

    except RPCError as e:
        if "not found" in str(e).lower():
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status="not_found",
                result=None
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow status: {str(e)}"
        )
