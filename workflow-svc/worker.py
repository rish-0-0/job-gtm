#!/usr/bin/env python
"""
Temporal Worker
This worker executes workflows and activities
"""
import asyncio
import logging
import os
from temporalio.client import Client
from temporalio.worker import Worker

from workflows.scrape_workflow import ScrapeWorkflow
from workflows.enrichment_workflow import EnrichmentWorkflow
from workflows.detail_scrape_workflow import DetailScrapeWorkflow, DetailScrapeChunkWorkflow
from activities.scrape_activities import (
    get_available_scrapers,
    call_scraper_service,
)
from activities.queue_activities import (
    publish_scrape_results,
)
from activities.enrichment_activities import (
    fetch_jobs_for_enrichment,
    publish_to_raw_jobs_queue,
)
from activities.detail_scrape_activities import (
    get_jobs_chunk_info,
    fetch_jobs_chunk,
    scrape_job_details,
    save_detail_scraped_job,
    publish_detail_scraped_jobs,
    get_detail_scrape_stats,
)
from queue_config import setup_queues, close_rabbitmq_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "job-gtm-queue")


async def main():
    """Main worker function"""
    logger.info(f"Connecting to Temporal at {TEMPORAL_ADDRESS}")

    # Connect to Temporal
    client = await Client.connect(TEMPORAL_ADDRESS)
    logger.info("Connected to Temporal successfully")

    # Setup RabbitMQ queues with retry
    logger.info("Setting up RabbitMQ queues...")
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        try:
            await setup_queues()
            logger.info("RabbitMQ queues setup complete")
            break
        except Exception as e:
            if attempt == max_attempts:
                logger.error(f"Failed to setup RabbitMQ queues after {max_attempts} attempts: {str(e)}")
                raise
            logger.warning(f"RabbitMQ setup failed (attempt {attempt}/{max_attempts}): {str(e)}, retrying in 2s...")
            await asyncio.sleep(2)

    # Create worker with increased concurrency
    logger.info(f"Starting worker on task queue: {TEMPORAL_TASK_QUEUE}")
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[
            ScrapeWorkflow,
            EnrichmentWorkflow,
            DetailScrapeWorkflow,
            DetailScrapeChunkWorkflow,  # Child workflow for chunked processing
        ],
        activities=[
            # Scrape activities
            get_available_scrapers,
            call_scraper_service,
            publish_scrape_results,
            # Enrichment activities
            fetch_jobs_for_enrichment,
            publish_to_raw_jobs_queue,
            # Detail scrape activities
            get_jobs_chunk_info,
            fetch_jobs_chunk,
            scrape_job_details,
            save_detail_scraped_job,
            publish_detail_scraped_jobs,
            get_detail_scrape_stats,
        ],
        max_concurrent_workflow_tasks=200,
        max_concurrent_activities=100,
    )

    logger.info("Worker started and ready to process workflows")
    logger.info(f"Registered workflows: {[w.__name__ for w in [ScrapeWorkflow, EnrichmentWorkflow, DetailScrapeWorkflow, DetailScrapeChunkWorkflow]]}")
    logger.info(f"Registered activities: get_jobs_chunk_info, fetch_jobs_chunk, scrape_job_details, save_detail_scraped_job, publish_detail_scraped_jobs, get_detail_scrape_stats")

    # Run the worker
    try:
        await worker.run()
    finally:
        # Cleanup RabbitMQ connection on shutdown
        await close_rabbitmq_connection()


if __name__ == "__main__":
    asyncio.run(main())
