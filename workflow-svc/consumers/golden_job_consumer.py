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

from sqlalchemy.sql import func

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
        We just need to UPDATE them with AI enrichment results using direct UPDATE by ID.
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

                    if not golden_id:
                        logger.warning(f"[Golden Consumer] ⚠️ No ID in message, skipping: {posting_url}")
                        await message.ack()
                        not_found_count += 1
                        continue

                    # Build update dict from enrichment data
                    update_values = self._build_update_dict(enriched_data)

                    # Direct UPDATE by ID - no SELECT needed
                    result = db.query(JobListingGolden).filter(
                        JobListingGolden.id == golden_id
                    ).update(update_values, synchronize_session=False)

                    db.commit()

                    if result > 0:
                        updated_count += 1
                        await message.ack()
                        logger.info(f"[Golden Consumer] ✅ Updated job id={golden_id}: {posting_url}")
                    else:
                        not_found_count += 1
                        await message.ack()  # Ack anyway - job doesn't exist
                        logger.warning(f"[Golden Consumer] ⚠️ Job not found id={golden_id}: {posting_url}")

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

    def _truncate(self, value: str, max_length: int) -> str:
        """Truncate string to max length, handling None and N/A"""
        if value is None:
            return None
        value = str(value).strip()
        # Keep N/A as a valid value instead of converting to None
        if len(value) > max_length:
            return value[:max_length]
        return value

    def _clean_na(self, value: str) -> str:
        """Convert N/A to None for optional fields, otherwise return value"""
        if value is None:
            return None
        value = str(value).strip()
        if value.upper() in ('N/A', 'NA', 'NONE', 'NULL', ''):
            return None
        return value

    def _sanitize_currency(self, currency: str) -> str:
        """Extract first currency code from potentially malformed LLM output"""
        if not currency:
            return None
        # LLM might return "INR|USD|EUR" - just take the first one
        currency = str(currency).strip()
        if currency.upper() in ('N/A', 'NA', 'NONE', 'NULL'):
            return None
        if '|' in currency:
            currency = currency.split('|')[0].strip()
        if '/' in currency:
            currency = currency.split('/')[0].strip()
        if ',' in currency:
            currency = currency.split(',')[0].strip()
        return currency[:10] if currency else None

    def _safe_number(self, value, default=None):
        """Safely convert value to number, treating 0 as valid"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return value if value != 0 else default  # 0 from LLM means "not available"
        try:
            num = float(value)
            return num if num != 0 else default
        except (ValueError, TypeError):
            return default

    def _safe_bool(self, value, default=False):
        """Safely convert value to boolean"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1')
        return bool(value)

    def _build_update_dict(self, enriched_data: dict) -> dict:
        """
        Build dictionary of fields to update from AI enrichment data.
        Returns a dict that can be passed directly to SQLAlchemy update().
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
        tech_stack = ai.get('tech_stack', {})
        skills = ai.get('skills_extraction', {})

        update = {}

        # Location normalization
        if location:
            city = self._clean_na(location.get('city'))
            state = self._clean_na(location.get('state'))
            country = self._clean_na(location.get('country'))
            timezone_str = self._clean_na(location.get('timezone'))

            # Build normalized location string
            location_parts = [p for p in [city, state, country] if p]
            if location_parts:
                update['job_location_normalized'] = self._truncate(', '.join(location_parts), 255)

            update['location_city'] = self._truncate(city, 100) if city else None
            update['location_state'] = self._truncate(state, 100) if state else None
            update['location_country'] = self._truncate(country, 100) if country else None
            update['location_timezone'] = self._truncate(timezone_str, 50) if timezone_str else None
            update['is_remote'] = self._safe_bool(location.get('is_remote'), False)

        # Salary normalization
        if currency_norm:
            update['currency_raw'] = self._sanitize_currency(currency_norm.get('detected_currency'))
            update['min_salary_usd'] = self._safe_number(currency_norm.get('min_salary_usd'))
            update['max_salary_usd'] = self._safe_number(currency_norm.get('max_salary_usd'))
            conversion_rate = self._safe_number(currency_norm.get('conversion_rate'))
            update['currency_conversion_rate'] = conversion_rate
            if conversion_rate:
                update['currency_conversion_date'] = datetime.now(timezone.utc)

        # Seniority normalization - always set even if N/A
        if seniority:
            normalized_seniority = self._clean_na(seniority.get('normalized'))
            update['seniority_level_normalized'] = self._truncate(normalized_seniority or 'N/A', 50)
            update['seniority_confidence_score'] = self._safe_number(seniority.get('confidence'))

        # Work arrangement - always set even if N/A
        if work_arr:
            normalized_work = self._clean_na(work_arr.get('normalized'))
            update['work_arrangement_normalized'] = self._truncate(normalized_work or 'N/A', 50)
            details = self._clean_na(work_arr.get('details'))
            update['work_arrangement_raw'] = self._truncate(details or 'N/A', 100)

        # Scam detection
        if scam:
            update['scam_score'] = self._safe_number(scam.get('score'), 0)
            indicators = scam.get('indicators', [])
            if isinstance(indicators, list):
                indicators = [i for i in indicators if self._clean_na(i)]
            update['scam_indicators'] = indicators if indicators else None

        # Skills extraction - store full skills array
        if skills:
            skills_list = skills.get('skills', [])
            if isinstance(skills_list, list) and skills_list:
                filtered_skills = [s for s in skills_list if isinstance(s, dict) and self._clean_na(s.get('skill'))]
                update['skills_extracted'] = filtered_skills if filtered_skills else None

        # Tech stack - combine all technology arrays
        if tech_stack:
            all_tech = []
            for key in ['technologies', 'frameworks', 'tools', 'databases', 'cloud']:
                tech_list = tech_stack.get(key, [])
                if isinstance(tech_list, list):
                    for t in tech_list:
                        cleaned = self._clean_na(t)
                        if cleaned and cleaned not in all_tech:
                            all_tech.append(cleaned)
            update['tech_stack_normalized'] = all_tech if all_tech else None

        # Company insights - always populate
        if company:
            notable_info = self._clean_na(company.get('notable_info'))
            update['company_research'] = notable_info or 'No additional company information available'
            industry = self._clean_na(company.get('industry'))
            update['company_industry'] = self._truncate(industry or 'N/A', 100)
            size = self._clean_na(company.get('company_size'))
            update['company_size'] = self._truncate(size or 'N/A', 100)

        # Benefits
        if benefits:
            update['has_stock_options'] = self._safe_bool(benefits.get('has_stock_options'), False)
            stock_details = self._clean_na(benefits.get('stock_details'))
            update['stock_options_details'] = stock_details
            other = benefits.get('other_benefits', [])
            if isinstance(other, list):
                other = [self._clean_na(b) for b in other if self._clean_na(b)]
            update['other_benefits'] = other if other else None

        # Role classification - always populate
        if role:
            primary = self._clean_na(role.get('primary_role'))
            update['primary_role'] = self._truncate(primary or 'N/A', 100)
            category = self._clean_na(role.get('role_category'))
            update['role_category'] = self._truncate(category or 'N/A', 100)
            update['is_management'] = self._safe_bool(role.get('is_management'), False)

        # Processing metadata
        update['enriched_at'] = self._parse_datetime(enriched_data.get('enriched_at')) or datetime.now(timezone.utc)
        update['ollama_model_version'] = self._truncate(metadata.get('model', 'llama3.2:3b'), 50)
        update['processing_duration_ms'] = enriched_data.get('processing_duration_ms')
        update['enrichment_status'] = self._truncate(enriched_data.get('enrichment_status', 'completed'), 50)
        update['ai_prompt_tokens'] = metadata.get('prompt_tokens')
        update['ai_response_tokens'] = metadata.get('response_tokens')

        # Store error if present
        if 'error' in ai:
            update['enrichment_errors'] = ai.get('error')

        # Update metadata
        update['updated_at'] = datetime.now(timezone.utc)
        # Increment enrichment_version, handling NULL with coalesce
        update['enrichment_version'] = func.coalesce(JobListingGolden.enrichment_version, 0) + 1

        return update

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
