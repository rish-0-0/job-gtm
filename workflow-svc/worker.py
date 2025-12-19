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
from activities.scrape_activities import (
    get_available_scrapers,
    call_scraper_service,
)
from activities.queue_activities import (
    publish_scrape_results,
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

    # Setup RabbitMQ queues
    logger.info("Setting up RabbitMQ queues...")
    try:
        await setup_queues()
        logger.info("RabbitMQ queues setup complete")
    except Exception as e:
        logger.error(f"Failed to setup RabbitMQ queues: {str(e)}")
        raise

    # Create worker with increased concurrency
    logger.info(f"Starting worker on task queue: {TEMPORAL_TASK_QUEUE}")
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[ScrapeWorkflow],
        activities=[
            get_available_scrapers,
            call_scraper_service,
            publish_scrape_results,
        ],
        max_concurrent_workflow_tasks=200,  # Allow more concurrent workflow executions
        max_concurrent_activities=100,  # Allow more concurrent activity executions
    )

    logger.info("Worker started and ready to process workflows")
    logger.info(f"Registered workflows: {[ScrapeWorkflow.__name__]}")
    logger.info(f"Registered activities: {['get_available_scrapers', 'call_scraper_service', 'publish_scrape_results']}")

    # Run the worker
    try:
        await worker.run()
    finally:
        # Cleanup RabbitMQ connection on shutdown
        await close_rabbitmq_connection()


if __name__ == "__main__":
    asyncio.run(main())
