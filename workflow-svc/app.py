from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import uuid
import logging
from datetime import datetime, timezone
from temporalio.client import Client
from workflows.scrape_workflow import ScrapeWorkflow
from workflows.enrichment_workflow import EnrichmentWorkflow
from workflows.detail_scrape_workflow import DetailScrapeWorkflow
from models import JobListing, JobListingGolden
from database import SessionLocal
from const import MAX_PAGES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Workflow Service", version="1.0.0")

# Temporal configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "job-gtm-queue")

# Request/Response models
class AIWorkflowRequest(BaseModel):
    job_listings: list
    model_type: str
    params: Optional[Dict[str, Any]] = None

class EnrichmentRequest(BaseModel):
    batch_size: Optional[int] = 100
    skip_already_enriched: Optional[bool] = True


class DetailScrapeRequest(BaseModel):
    batch_size: Optional[int] = 10
    max_concurrent: Optional[int] = 5
    skip_already_scraped: Optional[bool] = True
    limit: Optional[int] = None

class WorkflowResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str

class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

@app.get("/")
async def root():
    return {
        "service": "Workflow Service",
        "version": "1.0.0",
        "temporal_address": TEMPORAL_ADDRESS
    }

@app.get("/health")
async def health():
    try:
        # Try to connect to Temporal
        client = await Client.connect(TEMPORAL_ADDRESS)
        return {
            "status": "healthy",
            "temporal": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "temporal": "disconnected",
            "error": str(e)
        }

@app.post("/workflows/scrape/trigger", response_model=WorkflowResponse)
async def trigger_scrape_workflow():
    """
    Trigger the scraping workflow to scrape all available scrapers
    No parameters required - workflow will discover and scrape all available scrapers
    """
    try:
        logger.info(f"Connecting to Temporal at {TEMPORAL_ADDRESS}")
        client = await Client.connect(TEMPORAL_ADDRESS)
        logger.info("Connected to Temporal successfully")

        # Generate unique workflow ID
        workflow_id = f"scrape-all-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        logger.info(f"Starting workflow with ID: {workflow_id}")

        # Start the scraping workflow
        handle = await client.start_workflow(
            ScrapeWorkflow.run,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
            # max_pages defaults to MAX_PAGES in the workflow
        )

        logger.info(f"Workflow started successfully - ID: {handle.id}, Run ID: {handle.result_run_id}")
        logger.info(f"Task Queue: {TEMPORAL_TASK_QUEUE}")
        logger.info(f"View workflow in Temporal UI: http://localhost:8233/namespaces/default/workflows/{handle.id}")

        return WorkflowResponse(
            workflow_id=handle.id,
            run_id=handle.result_run_id,
            status="started"
        )
    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

@app.post("/workflows/scrape/trigger/{scraper}", response_model=WorkflowResponse)
async def trigger_single_scraper_workflow(scraper: str):
    """
    Trigger the scraping workflow for a specific scraper

    Args:
        scraper: Name of the scraper (e.g., 'dice', 'simplyhired', 'ziprecruiter')

    Returns:
        WorkflowResponse with workflow_id, run_id, and status
    """
    try:
        logger.info(f"Connecting to Temporal at {TEMPORAL_ADDRESS}")
        client = await Client.connect(TEMPORAL_ADDRESS)
        logger.info("Connected to Temporal successfully")

        # Generate unique workflow ID
        workflow_id = f"scrape-{scraper}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        logger.info(f"Starting workflow with ID: {workflow_id} for scraper: {scraper}")

        # Start the scraping workflow with specific scraper
        handle = await client.start_workflow(
            ScrapeWorkflow.run,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
            args=[MAX_PAGES, scraper],  # max_pages=MAX_PAGES, scraper_name=scraper
        )

        logger.info(f"Workflow started successfully - ID: {handle.id}, Run ID: {handle.result_run_id}")
        logger.info(f"Task Queue: {TEMPORAL_TASK_QUEUE}")
        logger.info(f"Scraper: {scraper}")
        logger.info(f"View workflow in Temporal UI: http://localhost:8233/namespaces/default/workflows/{handle.id}")

        return WorkflowResponse(
            workflow_id=handle.id,
            run_id=handle.result_run_id,
            status="started"
        )
    except Exception as e:
        logger.error(f"Failed to start workflow for scraper {scraper}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

@app.post("/workflows/ai", response_model=WorkflowResponse)
async def start_ai_workflow(request: AIWorkflowRequest):
    """
    Start an AI processing workflow in Temporal
    """
    try:
        client = await Client.connect(TEMPORAL_ADDRESS)

        # TODO: Start the AI workflow with Temporal
        # For now, return a placeholder response

        return WorkflowResponse(
            workflow_id=f"ai-{request.model_type}-placeholder",
            run_id="placeholder-run-id",
            status="started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

@app.post("/workflows/enrich/trigger", response_model=WorkflowResponse)
async def trigger_enrichment_workflow(request: EnrichmentRequest = EnrichmentRequest()):
    """
    Trigger the enrichment workflow to process all existing job listings

    This will:
    1. Fetch all jobs from job_listings table
    2. Filter out already enriched jobs (if skip_already_enriched=True)
    3. Publish jobs to raw_jobs_for_processing queue
    4. AI consumer will process them asynchronously
    5. Enriched jobs will be stored in job_listings_golden table

    Args:
        batch_size: Number of jobs to publish per batch (default: 100)
        skip_already_enriched: Skip jobs already in golden table (default: True)
    """
    try:
        logger.info(f"Connecting to Temporal at {TEMPORAL_ADDRESS}")
        client = await Client.connect(TEMPORAL_ADDRESS)
        logger.info("Connected to Temporal successfully")

        workflow_id = f"enrich-all-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        logger.info(f"Starting enrichment workflow with ID: {workflow_id}")

        handle = await client.start_workflow(
            EnrichmentWorkflow.run,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
            args=[request.batch_size, request.skip_already_enriched]
        )

        logger.info(f"Enrichment workflow started: {workflow_id}")
        logger.info(f"View workflow in Temporal UI: http://localhost:8233/namespaces/default/workflows/{handle.id}")

        return WorkflowResponse(
            workflow_id=handle.id,
            run_id=handle.result_run_id,
            status="started"
        )
    except Exception as e:
        logger.error(f"Failed to start enrichment workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/enrichment/status")
async def get_enrichment_status():
    """
    Get current enrichment pipeline status
    Returns counts of jobs in each stage
    """
    db = SessionLocal()
    try:
        total_jobs = db.query(JobListing).count()
        enriched_jobs = db.query(JobListingGolden).filter(
            JobListingGolden.enrichment_status == 'completed'
        ).count()

        return {
            "total_jobs": total_jobs,
            "enriched_jobs": enriched_jobs,
            "pending_enrichment": total_jobs - enriched_jobs,
            "enrichment_percentage": round((enriched_jobs / total_jobs * 100), 2) if total_jobs > 0 else 0,
            "message": f"{enriched_jobs} out of {total_jobs} jobs enriched"
        }
    except Exception as e:
        logger.error(f"Failed to get enrichment status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============== DETAIL SCRAPING ENDPOINTS ==============

@app.post("/workflows/detail-scrape/trigger", response_model=WorkflowResponse)
async def trigger_detail_scrape_workflow(request: DetailScrapeRequest = DetailScrapeRequest()):
    """
    Trigger the detail scraping workflow to scrape full job details from posting URLs.

    This is Phase 1 of the enrichment pipeline:
    1. Fetch jobs from job_listings table that haven't been detail-scraped
    2. For each job, visit the posting URL and scrape full details
    3. Save scraped details to job_listings_golden table
    4. Mark jobs as ready for AI enrichment (Phase 2)

    Args:
        batch_size: Number of jobs per batch (default: 10)
        max_concurrent: Maximum concurrent scraping operations (default: 5)
        skip_already_scraped: Skip jobs already detail-scraped (default: True)
        limit: Maximum total jobs to process (default: None = all)
    """
    try:
        logger.info(f"Connecting to Temporal at {TEMPORAL_ADDRESS}")
        client = await Client.connect(TEMPORAL_ADDRESS)
        logger.info("Connected to Temporal successfully")

        workflow_id = f"detail-scrape-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        logger.info(f"Starting detail scrape workflow with ID: {workflow_id}")
        logger.info(f"Config: batch_size={request.batch_size}, max_concurrent={request.max_concurrent}, limit={request.limit}")

        handle = await client.start_workflow(
            DetailScrapeWorkflow.run,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
            args=[request.batch_size, request.max_concurrent, request.skip_already_scraped, request.limit]
        )

        logger.info(f"Detail scrape workflow started: {workflow_id}")
        logger.info(f"View workflow in Temporal UI: http://localhost:8233/namespaces/default/workflows/{handle.id}")

        return WorkflowResponse(
            workflow_id=handle.id,
            run_id=handle.result_run_id,
            status="started"
        )
    except Exception as e:
        logger.error(f"Failed to start detail scrape workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/detail-scrape/status")
async def get_detail_scrape_status():
    """
    Get current detail scraping pipeline status.
    Returns counts of jobs in each stage of the pipeline.
    """
    db = SessionLocal()
    try:
        total_raw = db.query(JobListing).count()
        total_golden = db.query(JobListingGolden).count()

        detail_scraped = db.query(JobListingGolden).filter(
            JobListingGolden.detail_scrape_status == 'completed'
        ).count()

        detail_failed = db.query(JobListingGolden).filter(
            JobListingGolden.detail_scrape_status == 'failed'
        ).count()

        pending_enrichment = db.query(JobListingGolden).filter(
            JobListingGolden.detail_scrape_status == 'completed',
            JobListingGolden.enrichment_status == 'pending'
        ).count()

        enriched = db.query(JobListingGolden).filter(
            JobListingGolden.enrichment_status == 'completed'
        ).count()

        not_yet_processed = total_raw - total_golden

        return {
            "pipeline_status": {
                "phase_1_detail_scraping": {
                    "total_raw_jobs": total_raw,
                    "not_yet_processed": not_yet_processed,
                    "detail_scraped": detail_scraped,
                    "detail_failed": detail_failed,
                    "scrape_percentage": round((detail_scraped / total_raw * 100), 2) if total_raw > 0 else 0
                },
                "phase_2_ai_enrichment": {
                    "pending_enrichment": pending_enrichment,
                    "enriched": enriched,
                    "enrichment_percentage": round((enriched / detail_scraped * 100), 2) if detail_scraped > 0 else 0
                }
            },
            "summary": {
                "total_raw_jobs": total_raw,
                "fully_processed": enriched,
                "overall_percentage": round((enriched / total_raw * 100), 2) if total_raw > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Failed to get detail scrape status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/workflows/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get the status of a running workflow
    """
    try:
        logger.info(f"Fetching status for workflow: {workflow_id}")
        client = await Client.connect(TEMPORAL_ADDRESS)

        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)

        # Describe the workflow to get its status
        description = await handle.describe()
        logger.info(f"Workflow {workflow_id} status: {description.status.name}")

        # Map Temporal workflow status to our status
        status_map = {
            "RUNNING": "running",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "CANCELED": "canceled",
            "TERMINATED": "terminated",
            "CONTINUED_AS_NEW": "running",
            "TIMED_OUT": "timed_out"
        }

        status = status_map.get(description.status.name, "unknown")

        # Try to get the result if workflow is completed
        result = None
        if status == "completed":
            try:
                result = await handle.result()
                logger.info(f"Workflow {workflow_id} result: {result}")
            except Exception as e:
                logger.warning(f"Could not get result for workflow {workflow_id}: {str(e)}")

        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            run_id=description.run_id,
            status=status,
            result=result
        )
    except Exception as e:
        logger.error(f"Failed to get workflow status for {workflow_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
