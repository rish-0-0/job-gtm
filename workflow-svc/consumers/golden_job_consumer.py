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

from sqlalchemy.exc import IntegrityError
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
        1. Parse enriched data
        2. Map to JobListingGolden model
        3. Bulk insert with duplicate handling
        """
        db = SessionLocal()
        inserted_count = 0
        updated_count = 0
        failed_count = 0

        try:
            for message in messages:
                try:
                    enriched_data = json.loads(message.body.decode())
                    posting_url = enriched_data.get('posting_url', 'unknown')

                    logger.debug(f"[Golden Consumer] Processing job: {posting_url}")

                    # Map to golden model
                    golden_job = self._map_to_golden_model(enriched_data)

                    try:
                        db.add(golden_job)
                        db.flush()
                        inserted_count += 1
                        await message.ack()
                        logger.info(f"[Golden Consumer] ✅ Inserted new job: {posting_url}")

                    except IntegrityError:
                        # Duplicate posting_url - update existing record
                        db.rollback()
                        logger.debug(f"[Golden Consumer] Duplicate detected, updating: {posting_url}")
                        await self._update_existing(db, enriched_data)
                        updated_count += 1
                        await message.ack()
                        logger.info(f"[Golden Consumer] 🔄 Updated existing job: {posting_url}")

                except Exception as e:
                    db.rollback()
                    logger.error(
                        f"Failed to process message: {str(e)}",
                        exc_info=True
                    )
                    await self._handle_failed_message(message, str(e))
                    failed_count += 1

            db.commit()

            logger.info(
                f"[Golden Consumer] 📊 Batch results: "
                f"✅ {inserted_count} inserted, 🔄 {updated_count} updated, ❌ {failed_count} failed"
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

    def _map_to_golden_model(self, enriched_data: dict) -> JobListingGolden:
        """
        Map enriched JSON data to JobListingGolden model
        Extract nested AI enrichment fields
        """
        ai = enriched_data.get('ai_enrichment', {})
        metadata = ai.get('_metadata', {})

        # Extract currency normalization
        currency_norm = ai.get('currency_normalization', {})

        # Extract seniority level
        seniority = ai.get('seniority_level', {})

        # Extract work arrangement
        work_arr = ai.get('work_arrangement', {})

        # Extract scam detection
        scam = ai.get('scam_detection', {})

        # Extract location normalization
        location = ai.get('location_normalization', {})

        # Extract company insights
        company = ai.get('company_insights', {})

        # Extract benefits
        benefits = ai.get('benefits', {})

        # Extract role classification
        role = ai.get('role_classification', {})

        return JobListingGolden(
            source_job_id=enriched_data.get('id'),
            posting_url=enriched_data['posting_url'],

            # Core fields
            company_title=enriched_data.get('company_title'),
            job_role=enriched_data.get('job_role'),
            job_location_raw=enriched_data.get('job_location'),
            job_location_normalized=f"{location.get('city', '')}, {location.get('country', '')}".strip(', '),
            employment_type_raw=enriched_data.get('employment_type'),
            employment_type_normalized=enriched_data.get('employment_type'),

            # Salary normalization
            salary_range_raw=enriched_data.get('salary_range'),
            min_salary_raw=enriched_data.get('min_salary'),
            max_salary_raw=enriched_data.get('max_salary'),
            currency_raw=currency_norm.get('detected_currency'),
            min_salary_usd=currency_norm.get('min_salary_usd'),
            max_salary_usd=currency_norm.get('max_salary_usd'),
            currency_conversion_rate=currency_norm.get('conversion_rate'),
            currency_conversion_date=datetime.now(timezone.utc) if currency_norm.get('conversion_rate') else None,

            # Experience and seniority
            required_experience=enriched_data.get('required_experience'),
            seniority_level_raw=enriched_data.get('seniority_level'),
            seniority_level_normalized=seniority.get('normalized'),
            seniority_confidence_score=seniority.get('confidence'),

            # Work arrangement
            work_arrangement_raw=work_arr.get('details'),
            work_arrangement_normalized=work_arr.get('normalized'),

            # Scam detection
            scam_score=scam.get('score'),
            scam_indicators=scam.get('indicators'),

            # Skills
            skills_extracted=ai.get('skills_extraction', {}).get('skills'),
            tech_stack_normalized=ai.get('tech_stack', {}).get('technologies'),

            # Location details
            location_city=location.get('city'),
            location_state=location.get('state'),
            location_country=location.get('country'),
            location_timezone=location.get('timezone'),
            is_remote=location.get('is_remote'),

            # Company enrichment
            about_company_raw=enriched_data.get('about_company'),
            company_research=company.get('notable_info'),
            company_industry=company.get('industry'),
            company_size=company.get('company_size'),

            # Hiring team
            hiring_team_raw=enriched_data.get('hiring_team'),
            hiring_team_analysis=None,  # Could be added later

            # Benefits
            has_stock_options=benefits.get('has_stock_options'),
            stock_options_details=benefits.get('stock_details'),
            other_benefits=benefits.get('other_benefits'),

            # Full job details
            job_description_full=enriched_data.get('job_description_full', enriched_data.get('job_description')),
            job_requirements=enriched_data.get('job_requirements'),
            job_benefits=enriched_data.get('job_benefits'),

            # Role classification
            primary_role=role.get('primary_role'),
            role_category=role.get('role_category'),
            is_management=role.get('is_management'),

            # Additional metadata from raw job_listing
            date_posted=enriched_data.get('date_posted'),
            scraper_source=enriched_data.get('scraper_source'),
            scraped_at=self._parse_datetime(enriched_data.get('scraped_at')),

            # Processing metadata
            enriched_at=self._parse_datetime(enriched_data.get('enriched_at')) or datetime.now(timezone.utc),
            ollama_model_version=metadata.get('model', 'llama3.2:3b'),
            processing_duration_ms=enriched_data.get('processing_duration_ms'),
            ai_prompt_tokens=None,  # Could be extracted if available
            ai_response_tokens=None,
            enrichment_status=enriched_data.get('enrichment_status', 'completed'),
            enrichment_errors=ai.get('error') if 'error' in ai else None,
        )

    async def _update_existing(self, db, enriched_data: dict):
        """Update existing record with latest enrichment"""
        posting_url = enriched_data['posting_url']

        existing = db.query(JobListingGolden).filter(
            JobListingGolden.posting_url == posting_url
        ).first()

        if existing:
            # Update with new enrichment data
            golden_job = self._map_to_golden_model(enriched_data)

            # Update fields (excluding id and created_at)
            for key, value in vars(golden_job).items():
                if key not in ['_sa_instance_state', 'id', 'created_at']:
                    setattr(existing, key, value)

            existing.updated_at = datetime.now(timezone.utc)
            existing.enrichment_version = (existing.enrichment_version or 0) + 1

            db.commit()

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
