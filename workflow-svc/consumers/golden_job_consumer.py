"""
Golden Job Storage Consumer
Consumes enriched jobs from enriched_jobs queue
Stores in job_listings_golden table
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

from aio_pika import connect_robust
from aio_pika.abc import AbstractIncomingMessage

from database import SessionLocal
from models import JobListingGolden
from queue_config import RABBITMQ_URL, ENRICHED_JOBS_QUEUE, ENRICHED_JOBS_DLQ
from const import ENRICHMENT_MAX_RETRIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Consumer configuration
BATCH_SIZE = 50
BATCH_TIMEOUT = 2.0


class GoldenJobConsumer:
    """
    Consumer to store enriched jobs in job_listings_golden table
    """

    def __init__(self):
        self.running = False
        self.message_batch: List[AbstractIncomingMessage] = []
        self.batch_lock = asyncio.Lock()
        self.batch_event = asyncio.Event()

    async def process_message(self, message: AbstractIncomingMessage):
        """Add message to batch"""
        async with self.batch_lock:
            self.message_batch.append(message)
            if len(self.message_batch) >= BATCH_SIZE:
                self.batch_event.set()

    async def batch_processor(self):
        """Process messages in batches"""
        while self.running:
            try:
                # Wait for batch to fill or timeout
                try:
                    await asyncio.wait_for(
                        self.batch_event.wait(),
                        timeout=BATCH_TIMEOUT
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
                logger.info(f"[Golden Consumer] ━━━ Processing batch of {len(batch)} enriched jobs ━━━")
                batch_start = datetime.now(timezone.utc)
                await self._process_batch(batch)
                batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()
                logger.info(f"[Golden Consumer] ━━━ Batch completed in {batch_duration:.2f}s ━━━")

            except Exception as e:
                logger.error(f"Error in batch processor: {str(e)}", exc_info=True)

    async def _process_batch(self, messages: List[AbstractIncomingMessage]):
        """
        Process batch of enriched jobs:
        Jobs already exist in golden table from detail scraping phase.
        We just need to UPDATE them with AI enrichment results.
        """
        db = SessionLocal()
        updated_count = 0
        not_found_count = 0
        failed_count = 0

        try:
            for message in messages:
                try:
                    enriched_data = json.loads(message.body.decode())
                    posting_url = enriched_data.get('posting_url', 'unknown')
                    golden_id = enriched_data.get('id')  # This is the golden table ID

                    logger.debug(f"[Golden Consumer] Processing job: {posting_url} (id={golden_id})")

                    # Find existing record by ID or posting_url
                    existing = None
                    if golden_id:
                        existing = db.query(JobListingGolden).filter(
                            JobListingGolden.id == golden_id
                        ).first()

                    if not existing:
                        existing = db.query(JobListingGolden).filter(
                            JobListingGolden.posting_url == posting_url
                        ).first()

                    if existing:
                        # Update with AI enrichment data
                        self._update_with_enrichment(existing, enriched_data)
                        db.commit()
                        updated_count += 1
                        await message.ack()
                        logger.info(f"[Golden Consumer] ✅ Updated job with AI enrichment: {posting_url}")
                    else:
                        logger.warning(f"[Golden Consumer] ⚠️ Job not found in golden table: {posting_url}")
                        not_found_count += 1
                        await message.ack()  # Ack anyway - job doesn't exist

                except Exception as e:
                    db.rollback()
                    logger.error(
                        f"Failed to process message: {str(e)}",
                        exc_info=True
                    )
                    await self._handle_failed_message(message, str(e))
                    failed_count += 1

            logger.info(
                f"[Golden Consumer] 📊 Batch results: "
                f"✅ {updated_count} updated, ⚠️ {not_found_count} not found, ❌ {failed_count} failed"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Batch processing error: {str(e)}", exc_info=True)
        finally:
            db.close()

    def _parse_datetime(self, dt_string):
        """
        Safely parse datetime string, handling various formats
        """
        if not dt_string:
            return None
        try:
            # Try parsing ISO format
            return datetime.fromisoformat(dt_string)
        except (ValueError, TypeError):
            # If that fails, return None
            logger.warning(f"Could not parse datetime: {dt_string}")
            return None

    def _update_with_enrichment(self, existing: JobListingGolden, enriched_data: dict):
        """
        Update existing golden record with AI enrichment data.
        Only updates enrichment-related fields, preserves original scraped data.
        """
        ai = enriched_data.get('ai_enrichment', {})
        metadata = ai.get('_metadata', {})

        # Extract AI enrichment fields
        currency_norm = ai.get('currency_normalization', {})
        seniority = ai.get('seniority_level', {})
        work_arr = ai.get('work_arrangement', {})
        scam = ai.get('scam_detection', {})
        location = ai.get('location_normalization', {})
        company = ai.get('company_insights', {})
        benefits = ai.get('benefits', {})
        role = ai.get('role_classification', {})

        # Update normalized/enriched fields only
        # Location normalization
        if location:
            city = location.get('city', '')
            country = location.get('country', '')
            if city or country:
                existing.job_location_normalized = f"{city}, {country}".strip(', ')
            existing.location_city = location.get('city')
            existing.location_state = location.get('state')
            existing.location_country = location.get('country')
            existing.location_timezone = location.get('timezone')
            if location.get('is_remote') is not None:
                existing.is_remote = location.get('is_remote')

        # Salary normalization
        if currency_norm:
            existing.currency_raw = currency_norm.get('detected_currency')
            existing.min_salary_usd = currency_norm.get('min_salary_usd')
            existing.max_salary_usd = currency_norm.get('max_salary_usd')
            existing.currency_conversion_rate = currency_norm.get('conversion_rate')
            if currency_norm.get('conversion_rate'):
                existing.currency_conversion_date = datetime.now(timezone.utc)

        # Seniority normalization
        if seniority:
            existing.seniority_level_normalized = seniority.get('normalized')
            existing.seniority_confidence_score = seniority.get('confidence')

        # Work arrangement
        if work_arr:
            existing.work_arrangement_raw = work_arr.get('details')
            existing.work_arrangement_normalized = work_arr.get('normalized')

        # Scam detection
        if scam:
            existing.scam_score = scam.get('score')
            existing.scam_indicators = scam.get('indicators')

        # Skills extraction
        skills = ai.get('skills_extraction', {})
        if skills:
            existing.skills_extracted = skills.get('skills')

        tech_stack = ai.get('tech_stack', {})
        if tech_stack:
            existing.tech_stack_normalized = tech_stack.get('technologies')

        # Company insights
        if company:
            existing.company_research = company.get('notable_info')
            existing.company_industry = company.get('industry')
            existing.company_size = company.get('company_size')

        # Benefits
        if benefits:
            existing.has_stock_options = benefits.get('has_stock_options')
            existing.stock_options_details = benefits.get('stock_details')
            existing.other_benefits = benefits.get('other_benefits')

        # Role classification
        if role:
            existing.primary_role = role.get('primary_role')
            existing.role_category = role.get('role_category')
            existing.is_management = role.get('is_management')

        # Processing metadata
        existing.enriched_at = self._parse_datetime(enriched_data.get('enriched_at')) or datetime.now(timezone.utc)
        existing.ollama_model_version = metadata.get('model', 'llama3.2:3b')
        existing.processing_duration_ms = enriched_data.get('processing_duration_ms')
        existing.enrichment_status = enriched_data.get('enrichment_status', 'completed')

        # Store error if present
        if 'error' in ai:
            existing.enrichment_errors = ai.get('error')

        # Update metadata
        existing.updated_at = datetime.now(timezone.utc)
        existing.enrichment_version = (existing.enrichment_version or 0) + 1

    async def _handle_failed_message(self, message: AbstractIncomingMessage, error: str):
        """Handle failed message with retry logic"""
        try:
            retry_count = message.headers.get('x-retry-count', 0) if message.headers else 0
            retry_count += 1

            if retry_count <= ENRICHMENT_MAX_RETRIES:
                logger.warning(
                    f"Requeuing message (attempt {retry_count}/{ENRICHMENT_MAX_RETRIES})"
                )
                await message.nack(requeue=True)
            else:
                logger.error(
                    f"Max retries exceeded, sending to DLQ: {error}"
                )
                await message.reject(requeue=False)

        except Exception as e:
            logger.error(f"Error handling failed message: {str(e)}")

    async def start(self):
        """Start the consumer"""
        self.running = True
        logger.info("Starting Golden Job Storage Consumer...")

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
            await channel.set_qos(prefetch_count=BATCH_SIZE * 2)

            queue = await channel.get_queue(ENRICHED_JOBS_QUEUE)
            logger.info(f"Connected to queue: {ENRICHED_JOBS_QUEUE}")

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

        logger.info("Golden Job Storage Consumer stopped")

    def stop(self):
        """Stop the consumer"""
        logger.info("Stopping Golden Job Storage Consumer...")
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
    consumer = GoldenJobConsumer()

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
