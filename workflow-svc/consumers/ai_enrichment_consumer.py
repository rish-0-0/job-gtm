"""
AI Enrichment Consumer
Consumes raw jobs from raw_jobs_for_processing queue
Performs deep scraping + AI enrichment
Publishes to enriched_jobs queue
"""
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aio_pika import connect_robust, Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage

from queue_config import (
    RABBITMQ_URL, RAW_JOBS_QUEUE, ENRICHED_JOBS_QUEUE,
    ENRICHED_JOBS_EXCHANGE, RAW_JOBS_DLQ
)
from const import (
    ENRICHMENT_BATCH_SIZE, ENRICHMENT_BATCH_TIMEOUT,
    OLLAMA_RATE_LIMIT, ENRICHMENT_MAX_RETRIES
)
from services.ollama_client import OllamaClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIEnrichmentConsumer:
    """
    Consumer for AI enrichment of job listings
    """

    def __init__(self):
        self.ollama_client = OllamaClient()
        self.running = False
        self.message_batch: List[AbstractIncomingMessage] = []
        self.batch_lock = asyncio.Lock()
        self.batch_event = asyncio.Event()

        # Rate limiter for Ollama (no need for puppeteer - data already scraped)
        self.ollama_semaphore = asyncio.Semaphore(OLLAMA_RATE_LIMIT)

    async def process_message(self, message: AbstractIncomingMessage):
        """Add message to batch"""
        async with self.batch_lock:
            self.message_batch.append(message)
            if len(self.message_batch) >= ENRICHMENT_BATCH_SIZE:
                self.batch_event.set()

    async def batch_processor(self):
        """Process messages in batches"""
        while self.running:
            try:
                # Wait for batch to fill or timeout
                try:
                    await asyncio.wait_for(
                        self.batch_event.wait(),
                        timeout=ENRICHMENT_BATCH_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    pass

                # Get current batch
                async with self.batch_lock:
                    if not self.message_batch:
                        self.batch_event.clear()
                        continue

                    batch = self.message_batch.copy()
                    self.message_batch.clear()
                    self.batch_event.clear()

                # Process batch
                logger.info(f"[AI Consumer] ━━━ Processing batch of {len(batch)} jobs for enrichment ━━━")
                batch_start = datetime.now(timezone.utc)
                await self._process_batch(batch)
                batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()
                logger.info(f"[AI Consumer] ━━━ Batch completed in {batch_duration:.2f}s ━━━")

            except Exception as e:
                logger.error(f"Error in batch processor: {str(e)}", exc_info=True)

    async def _process_batch(self, messages: List[AbstractIncomingMessage]):
        """
        Process batch of raw jobs:
        1. Deep scrape job URLs
        2. Enrich with Ollama AI
        3. Publish to enriched_jobs queue
        """
        enrichment_tasks = [
            self._enrich_single_job(message)
            for message in messages
        ]

        results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

        # Log results
        success_count = sum(1 for r in results if r is True)
        failed_count = sum(1 for r in results if r is not True)

        logger.info(
            f"Batch processing complete: {success_count} succeeded, "
            f"{failed_count} failed"
        )

    async def _enrich_single_job(self, message: AbstractIncomingMessage) -> bool:
        """
        Enrich a single job listing:
        1. Parse message to get job data (already contains full details from golden table)
        2. Call Ollama for AI enrichment (with rate limiting)
        3. Publish enriched result
        4. Ack/nack message

        Note: Jobs come from golden table with job_description_full and full_page_text
        already populated from detail scraping phase. No need to scrape again.
        """
        try:
            start_time = datetime.now(timezone.utc)
            job_data = json.loads(message.body.decode())

            logger.info(
                f"Enriching job: {job_data.get('company_title')} - "
                f"{job_data.get('job_role')}"
            )

            # Job data already contains full details from golden table (detail scraping phase)
            # No need to deep scrape again - just use the data we have

            # AI enrichment (with rate limiting) - use job_data directly from golden table
            ai_enrichment = {}
            ai_start = datetime.now(timezone.utc)
            try:
                logger.debug(f"[AI Consumer] Acquiring Ollama semaphore for {job_data['posting_url']}")
                async with self.ollama_semaphore:
                    logger.info(f"[AI Consumer] Starting AI enrichment for {job_data['posting_url']}")
                    ai_enrichment = await self.ollama_client.enrich_job_listing(
                        job_data  # Use job_data directly - already has full details from golden table
                    )
                    ai_duration = (datetime.now(timezone.utc) - ai_start).total_seconds()
                    logger.info(f"[AI Consumer] AI enrichment completed in {ai_duration:.2f}s for {job_data['posting_url']}")
            except Exception as e:
                logger.error(
                    f"[AI Consumer] AI enrichment failed for {job_data['posting_url']}: {str(e)}"
                )
                ai_enrichment = {"error": str(e)}

            # Combine job data with AI enrichment results
            end_time = datetime.now(timezone.utc)
            total_duration = int((end_time - start_time).total_seconds() * 1000)
            enrichment_status = 'completed' if 'error' not in ai_enrichment else 'partial'

            final_data = {
                **job_data,  # Original data from golden table
                'ai_enrichment': ai_enrichment,
                'enriched_at': end_time.isoformat(),
                'enrichment_status': enrichment_status,
                'processing_duration_ms': total_duration
            }

            logger.info(
                f"[AI Consumer] Combined enrichment data for {job_data['posting_url']}: "
                f"status={enrichment_status}, total_duration={total_duration}ms"
            )

            # Step 4: Publish to enriched_jobs queue
            logger.debug(f"[AI Consumer] Publishing to enriched_jobs queue: {job_data['posting_url']}")
            await self._publish_to_enriched_queue(final_data)
            logger.info(f"[AI Consumer] Published to enriched_jobs queue: {job_data['posting_url']}")

            # Ack message
            await message.ack()
            logger.info(f"[AI Consumer] ✅ Successfully enriched job: {job_data['posting_url']} (total: {total_duration}ms)")
            return True

        except Exception as e:
            logger.error(
                f"Enrichment failed: {str(e)}",
                exc_info=True
            )
            await self._handle_failed_message(message, str(e))
            return False

    async def _publish_to_enriched_queue(self, data: dict):
        """Publish enriched job to enriched_jobs queue"""
        try:
            connection = await connect_robust(RABBITMQ_URL)
            async with connection:
                channel = await connection.channel()
                exchange = await channel.get_exchange(ENRICHED_JOBS_EXCHANGE)

                message = Message(
                    body=json.dumps(data).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    headers={
                        "source_job_id": data.get('id'),
                        "posting_url": data['posting_url'],
                        "enrichment_status": data.get('enrichment_status')
                    }
                )

                await exchange.publish(message, routing_key=ENRICHED_JOBS_QUEUE)
                logger.debug(f"Published enriched job to queue: {data['posting_url']}")

        except Exception as e:
            logger.error(f"Failed to publish to enriched queue: {str(e)}")
            raise

    async def _handle_failed_message(self, message: AbstractIncomingMessage, error: str):
        """Handle failed message with retry logic"""
        try:
            retry_count = message.headers.get('x-retry-count', 0) if message.headers else 0
            retry_count += 1

            if retry_count <= ENRICHMENT_MAX_RETRIES:
                logger.warning(
                    f"Requeuing message (attempt {retry_count}/{ENRICHMENT_MAX_RETRIES})"
                )
                # Update retry count and requeue
                await message.nack(requeue=True)
            else:
                logger.error(
                    f"Max retries exceeded, sending to DLQ: {error}"
                )
                # Reject and send to DLQ
                await message.reject(requeue=False)

        except Exception as e:
            logger.error(f"Error handling failed message: {str(e)}")

    async def start(self):
        """Start the consumer"""
        self.running = True
        logger.info("Starting AI Enrichment Consumer...")

        # Check Ollama health
        if await self.ollama_client.health_check():
            logger.info("Ollama service is healthy")
        else:
            logger.warning("Ollama service health check failed")

        # Connect to RabbitMQ with retry
        max_attempts = 30
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Connecting to RabbitMQ (attempt {attempt}/{max_attempts})...")
                connection = await connect_robust(RABBITMQ_URL)
                break
            except Exception as e:
                if attempt == max_attempts:
                    logger.error("Failed to connect to RabbitMQ after max attempts")
                    raise
                logger.warning(f"RabbitMQ connection failed: {e}, retrying...")
                await asyncio.sleep(2)

        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=ENRICHMENT_BATCH_SIZE * 2)

            queue = await channel.get_queue(RAW_JOBS_QUEUE)
            logger.info(f"Connected to queue: {RAW_JOBS_QUEUE}")

            # Start batch processor
            batch_processor_task = asyncio.create_task(self.batch_processor())

            # Start consuming
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.running:
                        break
                    await self.process_message(message)

            # Cleanup
            batch_processor_task.cancel()
            try:
                await batch_processor_task
            except asyncio.CancelledError:
                pass

        logger.info("AI Enrichment Consumer stopped")

    def stop(self):
        """Stop the consumer"""
        logger.info("Stopping AI Enrichment Consumer...")
        self.running = False


# Signal handlers for graceful shutdown
def signal_handler(consumer):
    def handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        consumer.stop()
        sys.exit(0)
    return handler


async def main():
    """Main entry point"""
    consumer = AIEnrichmentConsumer()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler(consumer))
    signal.signal(signal.SIGTERM, signal_handler(consumer))

    try:
        await consumer.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        consumer.stop()
    except Exception as e:
        logger.error(f"Consumer error: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
