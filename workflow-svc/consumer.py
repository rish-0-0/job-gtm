"""
RabbitMQ consumer for processing scraped job listings and writing to database
"""
import asyncio
import json
import logging
import os
import signal
from typing import List, Dict, Any
from datetime import datetime, timezone

from aio_pika import connect_robust, IncomingMessage
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.job_listing import JobListing
from queue_config import (
    RABBITMQ_URL,
    JOBS_QUEUE,
    JOBS_DLQ,
    setup_queues,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Batch configuration
BATCH_SIZE = 50  # Process up to 50 messages in a batch
BATCH_TIMEOUT = 2.0  # Wait up to 2 seconds to collect a batch
MAX_RETRIES = 3  # Maximum number of retries before sending to DLQ


class JobListingConsumer:
    """
    Consumer that processes scraped job listings from RabbitMQ queue
    """

    def __init__(self):
        self.running = False
        self.message_batch: List[AbstractIncomingMessage] = []
        self.batch_lock = asyncio.Lock()
        self.batch_event = asyncio.Event()

    async def process_message(self, message: IncomingMessage) -> None:
        """
        Add message to batch for processing
        """
        async with self.batch_lock:
            self.message_batch.append(message)

            # If batch is full, trigger processing
            if len(self.message_batch) >= BATCH_SIZE:
                self.batch_event.set()

    async def batch_processor(self) -> None:
        """
        Process messages in batches
        """
        while self.running:
            try:
                # Wait for batch to fill or timeout
                try:
                    await asyncio.wait_for(
                        self.batch_event.wait(),
                        timeout=BATCH_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    pass  # Timeout is expected

                # Get the batch
                async with self.batch_lock:
                    if not self.message_batch:
                        continue

                    batch = self.message_batch.copy()
                    self.message_batch.clear()
                    self.batch_event.clear()

                # Process the batch
                await self._process_batch(batch)

            except Exception as e:
                logger.error(f"Error in batch processor: {str(e)}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_batch(self, messages: List[AbstractIncomingMessage]) -> None:
        """
        Process a batch of messages and write to database
        """
        if not messages:
            return

        logger.info(f"Processing batch of {len(messages)} messages")

        db: Session = SessionLocal()
        jobs_to_insert: List[JobListing] = []
        message_job_mapping: Dict[int, AbstractIncomingMessage] = {}

        try:
            # Parse all messages and prepare job listings
            for idx, message in enumerate(messages):
                try:
                    job_data = json.loads(message.body.decode())

                    # Create job listing object
                    job_listing = JobListing(
                        company_title=job_data.get("companyTitle", ""),
                        job_role=job_data.get("jobRole", ""),
                        job_location=job_data.get("jobLocation"),
                        employment_type=job_data.get("employmentType"),
                        salary_range=job_data.get("salaryRange"),
                        min_salary=job_data.get("minSalary"),
                        max_salary=job_data.get("maxSalary"),
                        required_experience=job_data.get("requiredExperience"),
                        seniority_level=job_data.get("seniorityLevel"),
                        job_description=job_data.get("jobDescription"),
                        date_posted=job_data.get("datePosted"),
                        posting_url=job_data.get("postingUrl"),
                        hiring_team=job_data.get("hiringTeam"),
                        about_company=job_data.get("aboutCompany"),
                        scraper_source=job_data.get("scraper_source"),
                        scraped_at=datetime.now(timezone.utc)
                    )

                    jobs_to_insert.append(job_listing)
                    message_job_mapping[idx] = message

                except Exception as e:
                    logger.error(f"Failed to parse message: {str(e)}")
                    # Reject malformed message
                    await message.reject(requeue=False)

            # Bulk insert all jobs
            if jobs_to_insert:
                inserted_count = 0
                duplicate_count = 0
                failed_messages = []

                # Insert jobs one by one to handle duplicates gracefully
                for idx, job in enumerate(jobs_to_insert):
                    message = message_job_mapping[idx]

                    try:
                        db.add(job)
                        db.flush()
                        inserted_count += 1

                        # Acknowledge successful insert
                        await message.ack()

                    except IntegrityError:
                        # Duplicate job listing
                        db.rollback()
                        duplicate_count += 1

                        # Acknowledge duplicate (no need to reprocess)
                        await message.ack()
                        logger.debug(f"Duplicate job skipped: {job.posting_url}")

                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed to insert job: {str(e)}")
                        failed_messages.append((message, job))

                # Commit successful inserts
                db.commit()

                logger.info(
                    f"Batch processed: {inserted_count} inserted, "
                    f"{duplicate_count} duplicates skipped, "
                    f"{len(failed_messages)} failed"
                )

                # Handle failed messages
                for message, job in failed_messages:
                    await self._handle_failed_message(message, job)

        except Exception as e:
            db.rollback()
            logger.error(f"Batch processing failed: {str(e)}", exc_info=True)

            # Reject all messages in batch for reprocessing
            for message in messages:
                await self._handle_failed_message(message, None)

        finally:
            db.close()

    async def _handle_failed_message(
        self,
        message: AbstractIncomingMessage,
        job: JobListing = None
    ) -> None:
        """
        Handle a failed message with retry logic
        """
        # Get retry count from message headers
        retry_count = 0
        if message.headers and "x-retry-count" in message.headers:
            retry_count = int(message.headers["x-retry-count"])

        if retry_count < MAX_RETRIES:
            # Increment retry count and requeue
            retry_count += 1
            logger.warning(
                f"Requeuing message (attempt {retry_count}/{MAX_RETRIES}): "
                f"{job.posting_url if job else 'unknown'}"
            )

            # Reject and requeue with updated retry count
            await message.reject(requeue=True)
        else:
            # Max retries exceeded, send to DLQ
            logger.error(
                f"Max retries exceeded, sending to DLQ: "
                f"{job.posting_url if job else 'unknown'}"
            )
            # Reject without requeue (will go to DLQ if configured)
            await message.reject(requeue=False)

    async def start(self) -> None:
        """
        Start the consumer
        """
        self.running = True
        logger.info(f"Starting job listing consumer, connecting to {RABBITMQ_URL}")

        # Retry connection to RabbitMQ with exponential backoff
        max_attempts = 30
        attempt = 0
        connection = None

        while attempt < max_attempts and connection is None:
            try:
                logger.info(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{max_attempts})...")
                connection = await connect_robust(RABBITMQ_URL)
                logger.info("Connected to RabbitMQ successfully")
            except Exception as e:
                attempt += 1
                if attempt >= max_attempts:
                    logger.error(f"Failed to connect to RabbitMQ after {max_attempts} attempts")
                    raise
                wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                logger.warning(f"Failed to connect to RabbitMQ: {str(e)}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        # Setup channel
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=BATCH_SIZE * 2)

        # Setup queues and exchanges
        await setup_queues()
        logger.info("Queue setup complete")

        # Get the queue
        queue = await channel.get_queue(JOBS_QUEUE)

        # Start batch processor
        batch_task = asyncio.create_task(self.batch_processor())

        logger.info(f"Consumer started, listening on queue: {JOBS_QUEUE}")
        logger.info(f"Batch size: {BATCH_SIZE}, Batch timeout: {BATCH_TIMEOUT}s")

        # Start consuming
        await queue.consume(self.process_message)

        # Keep running until stopped
        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            # Cleanup
            batch_task.cancel()
            await connection.close()
            logger.info("Consumer stopped")

    def stop(self) -> None:
        """
        Stop the consumer
        """
        logger.info("Stopping consumer...")
        self.running = False


# Global consumer instance
consumer = JobListingConsumer()


def signal_handler(signum, frame):
    """
    Handle shutdown signals
    """
    logger.info(f"Received signal {signum}, initiating shutdown...")
    consumer.stop()


async def main():
    """
    Main entry point
    """
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await consumer.start()
    except Exception as e:
        logger.error(f"Consumer error: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
