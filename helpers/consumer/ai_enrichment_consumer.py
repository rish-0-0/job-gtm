"""
AI Enrichment Consumer - Helper System
Consumes raw jobs from remote RabbitMQ (main laptop)
Performs AI enrichment using local Ollama
Publishes enriched results back to remote RabbitMQ

This is a standalone consumer that helps parallelize the enrichment workload.
"""
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import List

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
from ollama_client import OllamaClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIEnrichmentConsumer:
    """
    Consumer for AI enrichment of job listings.
    Connects to remote RabbitMQ and uses local Ollama for inference.
    """

    def __init__(self):
        self.ollama_client = OllamaClient()
        self.running = False
        self.message_batch: List[AbstractIncomingMessage] = []
        self.batch_lock = asyncio.Lock()
        self.batch_event = asyncio.Event()

        # Rate limiter for Ollama
        self.ollama_semaphore = asyncio.Semaphore(OLLAMA_RATE_LIMIT)

        # Publisher connection (will be initialized in start())
        self.publisher_connection = None
        self.publisher_channel = None
        self.enriched_exchange = None
        self.publisher_lock = asyncio.Lock()

        # Log configuration
        logger.info(f"[Helper Consumer] Configuration:")
        logger.info(f"  - RabbitMQ URL: {RABBITMQ_URL.split('@')[1] if '@' in RABBITMQ_URL else RABBITMQ_URL}")
        logger.info(f"  - Ollama URL: {self.ollama_client.base_url}")
        logger.info(f"  - Batch size: {ENRICHMENT_BATCH_SIZE}")
        logger.info(f"  - Ollama rate limit: {OLLAMA_RATE_LIMIT}")

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
                logger.info(f"[Helper Consumer] Processing batch of {len(batch)} jobs")
                batch_start = datetime.now(timezone.utc)
                await self._process_batch(batch)
                batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()
                logger.info(f"[Helper Consumer] Batch completed in {batch_duration:.2f}s")

            except Exception as e:
                logger.error(f"Error in batch processor: {str(e)}", exc_info=True)

    async def _process_batch(self, messages: List[AbstractIncomingMessage]):
        """
        Process batch of raw jobs:
        1. Enrich with Ollama AI
        2. Publish to enriched_jobs queue
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
        1. Parse message to get job data
        2. Call Ollama for AI enrichment (with rate limiting)
        3. Publish enriched result
        4. Ack/nack message
        """
        try:
            start_time = datetime.now(timezone.utc)
            job_data = json.loads(message.body.decode())

            logger.info(
                f"[Helper] Enriching job: {job_data.get('company_title')} - "
                f"{job_data.get('job_role')}"
            )

            # Debug: Log what data we have for enrichment
            job_desc_len = len(job_data.get('job_description_full') or '')
            full_text_len = len(job_data.get('full_page_text') or '')
            logger.info(
                f"[Helper] Job data received - "
                f"job_description_full: {job_desc_len} chars, "
                f"full_page_text: {full_text_len} chars"
            )

            # AI enrichment (with rate limiting)
            ai_enrichment = {}
            ai_start = datetime.now(timezone.utc)
            try:
                logger.debug(f"[Helper] Acquiring Ollama semaphore for {job_data['posting_url']}")
                async with self.ollama_semaphore:
                    logger.info(f"[Helper] Starting AI enrichment for {job_data['posting_url']}")
                    ai_enrichment = await self.ollama_client.enrich_job_listing(job_data)
                    ai_duration = (datetime.now(timezone.utc) - ai_start).total_seconds()
                    logger.info(f"[Helper] AI enrichment completed in {ai_duration:.2f}s")
            except Exception as e:
                logger.error(
                    f"[Helper] AI enrichment failed for {job_data['posting_url']}: {str(e)}"
                )
                ai_enrichment = {"error": str(e)}

            # Combine job data with AI enrichment results
            end_time = datetime.now(timezone.utc)
            total_duration = int((end_time - start_time).total_seconds() * 1000)
            enrichment_status = 'completed' if 'error' not in ai_enrichment else 'partial'

            final_data = {
                **job_data,  # Original data
                'ai_enrichment': ai_enrichment,
                'enriched_at': end_time.isoformat(),
                'enrichment_status': enrichment_status,
                'processing_duration_ms': total_duration,
                'enriched_by': 'helper-system'  # Mark as processed by helper
            }

            logger.info(
                f"[Helper] Combined enrichment data for {job_data['posting_url']}: "
                f"status={enrichment_status}, total_duration={total_duration}ms"
            )

            # Publish to enriched_jobs queue
            logger.debug(f"[Helper] Publishing to enriched_jobs queue: {job_data['posting_url']}")
            await self._publish_to_enriched_queue(final_data)
            logger.info(f"[Helper] Published to enriched_jobs queue: {job_data['posting_url']}")

            # Ack message
            await message.ack()
            logger.info(f"[Helper] Successfully enriched job: {job_data['posting_url']} (total: {total_duration}ms)")
            return True

        except Exception as e:
            logger.error(
                f"Enrichment failed: {str(e)}",
                exc_info=True
            )
            await self._handle_failed_message(message, str(e))
            return False

    async def _ensure_publisher_connection(self):
        """Ensure publisher connection and exchange are ready"""
        from aio_pika import ExchangeType

        async with self.publisher_lock:
            # Check if connection is still valid
            if self.publisher_connection is not None and not self.publisher_connection.is_closed:
                if self.publisher_channel is not None and not self.publisher_channel.is_closed:
                    return  # Connection is good

            # Create new connection
            logger.info("[Helper] Establishing publisher connection...")
            self.publisher_connection = await connect_robust(RABBITMQ_URL)
            self.publisher_channel = await self.publisher_connection.channel()

            # Declare exchange
            self.enriched_exchange = await self.publisher_channel.declare_exchange(
                ENRICHED_JOBS_EXCHANGE,
                ExchangeType.DIRECT,
                durable=True
            )
            logger.info("[Helper] Publisher connection established")

    async def _publish_to_enriched_queue(self, data: dict):
        """Publish enriched job to enriched_jobs queue"""
        try:
            # Ensure we have a valid connection
            await self._ensure_publisher_connection()

            message = Message(
                body=json.dumps(data).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={
                    "source_job_id": data.get('id'),
                    "posting_url": data['posting_url'],
                    "enrichment_status": data.get('enrichment_status'),
                    "enriched_by": "helper-system"
                }
            )

            await self.enriched_exchange.publish(message, routing_key=ENRICHED_JOBS_QUEUE)
            logger.debug(f"Published enriched job to queue: {data['posting_url']}")

        except Exception as e:
            logger.error(f"Failed to publish to enriched queue: {str(e)}")
            # Reset connection so next attempt will reconnect
            self.publisher_connection = None
            self.publisher_channel = None
            self.enriched_exchange = None
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
        logger.info("=" * 60)
        logger.info("  HELPER SYSTEM - AI Enrichment Consumer")
        logger.info("=" * 60)
        logger.info("")

        # Check Ollama health
        logger.info("Checking Ollama service health...")
        if await self.ollama_client.health_check():
            logger.info("Ollama service is healthy")
        else:
            logger.warning("Ollama service health check failed - will retry on first job")

        # Connect to RabbitMQ with retry
        # Mask password in URL for logging
        safe_url = RABBITMQ_URL
        if '@' in RABBITMQ_URL:
            parts = RABBITMQ_URL.split('@')
            safe_url = f"amqp://***:***@{parts[1]}"

        logger.info(f"Connecting to remote RabbitMQ at: {safe_url}")
        logger.info(f"(Full URL configured via RABBITMQ_URL environment variable)")

        max_attempts = 30
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Connection attempt {attempt}/{max_attempts}...")
                connection = await connect_robust(RABBITMQ_URL)
                logger.info("Successfully connected to RabbitMQ!")
                break
            except Exception as e:
                error_msg = str(e)
                if "Connection refused" in error_msg:
                    logger.error(f"Connection REFUSED - Is RabbitMQ running? Is the IP correct?")
                    logger.error(f"Check: 1) Main system running  2) IP in .env  3) Firewall allows port 5672")
                elif "timeout" in error_msg.lower():
                    logger.error(f"Connection TIMEOUT - Network issue or wrong IP address")
                elif "Authentication" in error_msg or "access" in error_msg.lower():
                    logger.error(f"Authentication FAILED - Check username/password in RABBITMQ_URL")

                if attempt == max_attempts:
                    logger.error("=" * 60)
                    logger.error("  FAILED TO CONNECT TO RABBITMQ")
                    logger.error("=" * 60)
                    logger.error(f"URL: {safe_url}")
                    logger.error(f"Error: {e}")
                    logger.error("")
                    logger.error("Troubleshooting:")
                    logger.error("1. Check RABBITMQ_URL in your .env file")
                    logger.error("2. Verify main system's IP address")
                    logger.error("3. Ensure RabbitMQ is running on main system")
                    logger.error("4. Check firewall allows port 5672")
                    logger.error("5. Test: telnet <main-ip> 5672")
                    logger.error("=" * 60)
                    raise
                logger.warning(f"RabbitMQ connection failed: {e}, retrying in 2s...")
                await asyncio.sleep(2)

        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=ENRICHMENT_BATCH_SIZE * 2)

            # Declare queue (idempotent - won't recreate if exists)
            # Must match the main system's queue configuration
            queue = await channel.declare_queue(
                RAW_JOBS_QUEUE,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "raw_jobs_dlx",
                    "x-dead-letter-routing-key": RAW_JOBS_QUEUE,
                }
            )
            logger.info(f"Connected to queue: {RAW_JOBS_QUEUE}")
            logger.info("")
            logger.info("=" * 60)
            logger.info("  Ready to process jobs!")
            logger.info("=" * 60)
            logger.info("")

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

            # Close publisher connection
            if self.publisher_connection and not self.publisher_connection.is_closed:
                await self.publisher_connection.close()
                logger.info("Publisher connection closed")

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
