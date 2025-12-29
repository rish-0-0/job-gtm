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
from typing import List, Optional

from aio_pika import connect_robust, Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection, AbstractChannel, AbstractExchange
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

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


class RobustRabbitMQ:
    """
    Reusable RabbitMQ connection manager with automatic reconnection.
    Handles heartbeat configuration and retry logic.
    """

    def __init__(self, url: str, name: str = "RabbitMQ"):
        self.url = self._add_heartbeat(url, heartbeat=0)
        self.name = name
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.lock = asyncio.Lock()

    @staticmethod
    def _add_heartbeat(url: str, heartbeat: int = 0) -> str:
        """Add heartbeat parameter to RabbitMQ URL."""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        query_params['heartbeat'] = [str(heartbeat)]
        new_query = urlencode(query_params, doseq=True)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))

    async def connect(self, max_attempts: int = 10, retry_delay: int = 5) -> AbstractChannel:
        """Connect to RabbitMQ with retry logic. Returns a channel."""
        async with self.lock:
            # Return existing connection if valid
            if self.connection and not self.connection.is_closed:
                if self.channel and not self.channel.is_closed:
                    return self.channel

            # Close stale connections
            await self._close_internal()

            # Connect with retries
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"[{self.name}] Connecting (attempt {attempt}/{max_attempts})...")
                    self.connection = await connect_robust(
                        self.url,
                        timeout=30,
                        reconnect_interval=5,
                    )
                    self.channel = await self.connection.channel()
                    logger.info(f"[{self.name}] Connected successfully")
                    return self.channel
                except Exception as e:
                    logger.warning(f"[{self.name}] Connection failed: {e}")
                    if attempt == max_attempts:
                        raise
                    await asyncio.sleep(retry_delay)

    async def _close_internal(self):
        """Close connection without lock (internal use)."""
        if self.connection and not self.connection.is_closed:
            try:
                await self.connection.close()
            except Exception:
                pass
        self.connection = None
        self.channel = None

    async def close(self):
        """Close the connection."""
        async with self.lock:
            await self._close_internal()
            logger.info(f"[{self.name}] Connection closed")

    async def reset(self):
        """Reset connection state (call after errors)."""
        async with self.lock:
            await self._close_internal()


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

        # Reusable connection manager for publishing
        self.publisher = RobustRabbitMQ(RABBITMQ_URL, name="Publisher")
        self.enriched_exchange: Optional[AbstractExchange] = None

        # Log configuration
        safe_url = RABBITMQ_URL.split('@')[1] if '@' in RABBITMQ_URL else RABBITMQ_URL
        logger.info(f"[Helper Consumer] Configuration:")
        logger.info(f"  - RabbitMQ URL: {safe_url}")
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
        """Process batch of raw jobs with AI enrichment."""
        enrichment_tasks = [
            self._enrich_single_job(message)
            for message in messages
        ]

        results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        failed_count = sum(1 for r in results if r is not True)

        logger.info(f"Batch complete: {success_count} succeeded, {failed_count} failed")

    async def _enrich_single_job(self, message: AbstractIncomingMessage) -> bool:
        """Enrich a single job listing."""
        try:
            start_time = datetime.now(timezone.utc)
            job_data = json.loads(message.body.decode())

            logger.info(f"[Helper] Enriching: {job_data.get('company_title')} - {job_data.get('job_role')}")

            # AI enrichment (with rate limiting)
            ai_enrichment = {}
            try:
                async with self.ollama_semaphore:
                    ai_enrichment = await self.ollama_client.enrich_job_listing(job_data)
            except Exception as e:
                logger.error(f"[Helper] AI enrichment failed: {str(e)}")
                ai_enrichment = {"error": str(e)}

            # Build final data
            end_time = datetime.now(timezone.utc)
            total_duration = int((end_time - start_time).total_seconds() * 1000)

            final_data = {
                **job_data,
                'ai_enrichment': ai_enrichment,
                'enriched_at': end_time.isoformat(),
                'enrichment_status': 'completed' if 'error' not in ai_enrichment else 'partial',
                'processing_duration_ms': total_duration,
                'enriched_by': 'helper-system'
            }

            # Publish to enriched_jobs queue
            await self._publish_with_retry(final_data)

            await message.ack()
            logger.info(f"[Helper] Done: {job_data['posting_url']} ({total_duration}ms)")
            return True

        except Exception as e:
            logger.error(f"Enrichment failed: {str(e)}", exc_info=True)
            await self._handle_failed_message(message, str(e))
            return False

    async def _publish_with_retry(self, data: dict, max_retries: int = 3):
        """Publish to enriched_jobs queue with retry logic."""
        for attempt in range(1, max_retries + 1):
            try:
                # Get/create connection and exchange
                channel = await self.publisher.connect()
                if not self.enriched_exchange or self.publisher.channel != channel:
                    self.enriched_exchange = await channel.declare_exchange(
                        ENRICHED_JOBS_EXCHANGE,
                        ExchangeType.DIRECT,
                        durable=True
                    )

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
                return  # Success

            except Exception as e:
                logger.warning(f"Publish failed (attempt {attempt}/{max_retries}): {e}")
                await self.publisher.reset()
                self.enriched_exchange = None

                if attempt < max_retries:
                    await asyncio.sleep(2 * attempt)
                else:
                    raise

    async def _handle_failed_message(self, message: AbstractIncomingMessage, error: str):
        """Handle failed message with retry logic."""
        try:
            retry_count = message.headers.get('x-retry-count', 0) if message.headers else 0
            retry_count += 1

            if retry_count <= ENRICHMENT_MAX_RETRIES:
                logger.warning(f"Requeuing (attempt {retry_count}/{ENRICHMENT_MAX_RETRIES})")
                await message.nack(requeue=True)
            else:
                logger.error(f"Max retries exceeded, sending to DLQ: {error}")
                await message.reject(requeue=False)
        except Exception as e:
            logger.error(f"Error handling failed message: {e}")

    async def start(self):
        """Start the consumer with automatic reconnection."""
        self.running = True
        logger.info("=" * 60)
        logger.info("  HELPER SYSTEM - AI Enrichment Consumer")
        logger.info("=" * 60)

        # Check Ollama health
        logger.info("Checking Ollama service health...")
        if await self.ollama_client.health_check():
            logger.info("Ollama service is healthy")
        else:
            logger.warning("Ollama health check failed - will retry on first job")

        # Create consumer connection manager
        consumer_conn = RobustRabbitMQ(RABBITMQ_URL, name="Consumer")

        # Main loop with auto-reconnect
        while self.running:
            try:
                channel = await consumer_conn.connect(max_attempts=30)
                await channel.set_qos(prefetch_count=ENRICHMENT_BATCH_SIZE * 2)

                queue = await channel.declare_queue(
                    RAW_JOBS_QUEUE,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": "raw_jobs_dlx",
                        "x-dead-letter-routing-key": RAW_JOBS_QUEUE,
                    }
                )

                logger.info(f"Connected to queue: {RAW_JOBS_QUEUE}")
                logger.info("=" * 60)
                logger.info("  Ready to process jobs!")
                logger.info("=" * 60)

                # Start batch processor
                batch_task = asyncio.create_task(self.batch_processor())

                try:
                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            if not self.running:
                                break
                            await self.process_message(message)
                finally:
                    batch_task.cancel()
                    try:
                        await batch_task
                    except asyncio.CancelledError:
                        pass

            except Exception as e:
                if not self.running:
                    break
                logger.error(f"Connection lost: {e}")
                logger.info("Reconnecting in 5 seconds...")
                await consumer_conn.reset()
                await self.publisher.reset()
                self.enriched_exchange = None
                await asyncio.sleep(5)

        # Cleanup
        await consumer_conn.close()
        await self.publisher.close()
        logger.info("AI Enrichment Consumer stopped")

    def stop(self):
        """Stop the consumer."""
        logger.info("Stopping AI Enrichment Consumer...")
        self.running = False


def signal_handler(consumer):
    def handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        consumer.stop()
        sys.exit(0)
    return handler


async def main():
    consumer = AIEnrichmentConsumer()
    signal.signal(signal.SIGINT, signal_handler(consumer))
    signal.signal(signal.SIGTERM, signal_handler(consumer))

    try:
        await consumer.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        consumer.stop()
    except Exception as e:
        logger.error(f"Consumer error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
