"""
Temporal activities for detail scraping workflow
"""
import os
import json
import logging
import traceback
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from temporalio import activity
from aio_pika import Message, DeliveryMode

from database import SessionLocal
from models import JobListing, JobListingGolden
from queue_config import (
    get_rabbitmq_channel,
    DETAIL_SCRAPED_JOBS_QUEUE,
    DETAIL_SCRAPED_JOBS_EXCHANGE
)

logger = logging.getLogger(__name__)

SCRAPER_URL = os.getenv("SCRAPER_URL", "http://scraper:6000")
SCRAPER_TIMEOUT = 60.0  # 60 seconds per job scrape


@activity.defn
async def get_jobs_chunk_info(chunk_size: int = 100) -> Dict[str, Any]:
    """
    Get total job count and chunk information for parallel processing.
    This is a lightweight activity that only fetches counts, not data.

    Args:
        chunk_size: Number of jobs per chunk

    Returns:
        Dictionary with total count, chunk count, and chunk definitions
    """
    db = SessionLocal()
    try:
        print(f"[Detail Scrape Activity] Getting job chunk info with chunk_size={chunk_size}...", flush=True)

        total_count = db.query(JobListing).count()
        print(f"[Detail Scrape Activity] Total jobs in table: {total_count}", flush=True)

        # Calculate chunks
        chunk_count = (total_count + chunk_size - 1) // chunk_size  # Ceiling division
        chunks = []
        for i in range(chunk_count):
            offset = i * chunk_size
            limit = min(chunk_size, total_count - offset)
            chunks.append({
                'chunk_index': i,
                'offset': offset,
                'limit': limit
            })

        print(f"[Detail Scrape Activity] Created {chunk_count} chunks", flush=True)

        return {
            'total_jobs': total_count,
            'chunk_size': chunk_size,
            'chunk_count': chunk_count,
            'chunks': chunks
        }

    except Exception as e:
        error_msg = f"[Detail Scrape Activity] ❌ Failed to get chunk info: {str(e)}"
        print(error_msg, flush=True)
        logger.error(error_msg)
        raise
    finally:
        db.close()


@activity.defn
async def fetch_jobs_chunk(offset: int, limit: int) -> List[Dict[str, Any]]:
    """
    Fetch a specific chunk of jobs for detail scraping.

    Args:
        offset: Starting position
        limit: Number of jobs to fetch

    Returns:
        List of job dictionaries
    """
    db = SessionLocal()
    try:
        print(f"[Detail Scrape Activity] Fetching chunk: offset={offset}, limit={limit}...", flush=True)

        jobs = db.query(JobListing).offset(offset).limit(limit).all()
        print(f"[Detail Scrape Activity] Query returned {len(jobs)} jobs", flush=True)

        result = []
        for job in jobs:
            result.append({
                'id': job.id,
                'posting_url': job.posting_url,
                'company_title': job.company_title,
                'job_role': job.job_role,
                'job_location': job.job_location,
                'employment_type': job.employment_type,
                'salary_range': job.salary_range,
                'min_salary': float(job.min_salary) if job.min_salary else None,
                'max_salary': float(job.max_salary) if job.max_salary else None,
                'required_experience': job.required_experience,
                'seniority_level': job.seniority_level,
                'job_description': job.job_description,
                'date_posted': job.date_posted,
                'hiring_team': job.hiring_team,
                'about_company': job.about_company,
                'scraper_source': job.scraper_source,
                'scraped_at': job.scraped_at.isoformat() if job.scraped_at else None,
            })

        print(f"[Detail Scrape Activity] ✅ Prepared chunk with {len(result)} jobs", flush=True)
        return result

    except Exception as e:
        error_msg = f"[Detail Scrape Activity] ❌ Failed to fetch chunk: {str(e)}"
        print(error_msg, flush=True)
        print(traceback.format_exc(), flush=True)
        logger.error(error_msg)
        raise
    finally:
        db.close()


@activity.defn
async def scrape_job_details(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape full details for a single job by calling the scraper service.

    Args:
        job: Job dictionary with posting_url

    Returns:
        Job dictionary merged with scraped details
    """
    posting_url = job['posting_url']
    start_time = datetime.now(timezone.utc)

    logger.info(f"[Detail Scrape Activity] 🔍 Scraping details for: {job.get('company_title')} - {job.get('job_role')}")
    logger.info(f"[Detail Scrape Activity] URL: {posting_url}")

    try:
        async with httpx.AsyncClient(timeout=SCRAPER_TIMEOUT) as client:
            response = await client.post(
                f"{SCRAPER_URL}/scrape-detail",
                json={"url": posting_url}
            )

            if response.status_code != 200:
                error_msg = f"Scraper returned status {response.status_code}"
                logger.error(f"[Detail Scrape Activity] ❌ {error_msg}")
                return {
                    **job,
                    'detail_scrape_success': False,
                    'detail_scrape_error': error_msg,
                    'detail_scrape_duration_ms': int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                }

            result = response.json()
            scrape_result = result.get('result', {})

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            logger.info(
                f"[Detail Scrape Activity] ✅ Scraped details in {duration_ms}ms - "
                f"Description: {len(scrape_result.get('jobDescriptionFull', ''))} chars, "
                f"PageText: {len(scrape_result.get('fullPageText', ''))} chars"
            )

            # Merge scraped details with original job data
            # We only get jobDescriptionFull and fullPageText now - AI will extract everything else
            return {
                **job,
                'detail_scrape_success': scrape_result.get('scrapeSuccess', False),
                'detail_scrape_error': scrape_result.get('scrapeError'),
                'detail_scrape_duration_ms': duration_ms,
                'job_description_full': scrape_result.get('jobDescriptionFull', ''),
                'full_page_text': scrape_result.get('fullPageText', ''),
            }

    except httpx.TimeoutException:
        error_msg = f"Timeout after {SCRAPER_TIMEOUT}s"
        logger.error(f"[Detail Scrape Activity] ❌ {error_msg} for {posting_url}")
        return {
            **job,
            'detail_scrape_success': False,
            'detail_scrape_error': error_msg,
            'detail_scrape_duration_ms': int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Detail Scrape Activity] ❌ Error scraping {posting_url}: {error_msg}")
        return {
            **job,
            'detail_scrape_success': False,
            'detail_scrape_error': error_msg,
            'detail_scrape_duration_ms': int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        }


@activity.defn
async def save_detail_scraped_job(job: Dict[str, Any]) -> bool:
    """
    Save a detail-scraped job to the golden table.

    Args:
        job: Job dictionary with scraped details

    Returns:
        True if saved successfully
    """
    db = SessionLocal()
    try:
        posting_url = job['posting_url']
        logger.info(f"[Detail Scrape Activity] 💾 Saving detail-scraped job: {job.get('company_title')} - {job.get('job_role')}")

        # Check if record already exists
        existing = db.query(JobListingGolden).filter(
            JobListingGolden.posting_url == posting_url
        ).first()

        now = datetime.now(timezone.utc)

        if existing:
            # Update existing record with detail scrape data
            # We only store the full description and page text - AI will extract everything else
            existing.job_description_full = job.get('job_description_full')
            existing.full_page_text = job.get('full_page_text')

            # Preserve original fields from raw job
            if not existing.hiring_team_raw and job.get('hiring_team'):
                existing.hiring_team_raw = job.get('hiring_team')
            if not existing.about_company_raw and job.get('about_company'):
                existing.about_company_raw = job.get('about_company')

            # Detail scrape metadata
            existing.detail_scraped_at = now
            existing.detail_scrape_status = 'completed' if job.get('detail_scrape_success') else 'failed'
            existing.detail_scrape_duration_ms = job.get('detail_scrape_duration_ms')
            if job.get('detail_scrape_error'):
                existing.detail_scrape_errors = {'error': job.get('detail_scrape_error')}

            # Set enrichment status to pending (ready for AI enrichment)
            if job.get('detail_scrape_success') and not existing.enrichment_status:
                existing.enrichment_status = 'pending'

            db.commit()
            logger.info(f"[Detail Scrape Activity] ✅ Updated existing golden record for {posting_url}")

        else:
            # Create new record with raw job data + full page text for AI enrichment
            golden_job = JobListingGolden(
                source_job_id=job.get('id'),
                posting_url=posting_url,

                # Core fields from raw job
                company_title=job.get('company_title'),
                job_role=job.get('job_role'),
                job_location_raw=job.get('job_location'),
                employment_type_raw=job.get('employment_type'),
                salary_range_raw=job.get('salary_range'),
                min_salary_raw=job.get('min_salary'),
                max_salary_raw=job.get('max_salary'),
                required_experience=job.get('required_experience'),
                seniority_level_raw=job.get('seniority_level'),

                # Detail scraped fields - the full content for AI to process
                job_description_full=job.get('job_description_full'),
                full_page_text=job.get('full_page_text'),

                # Original data from card scrape
                about_company_raw=job.get('about_company'),
                hiring_team_raw=job.get('hiring_team'),

                # Metadata from raw
                date_posted=job.get('date_posted'),
                scraper_source=job.get('scraper_source'),
                scraped_at=datetime.fromisoformat(job['scraped_at']) if job.get('scraped_at') else None,

                # Detail scrape metadata
                detail_scraped_at=now,
                detail_scrape_status='completed' if job.get('detail_scrape_success') else 'failed',
                detail_scrape_duration_ms=job.get('detail_scrape_duration_ms'),
                detail_scrape_errors={'error': job.get('detail_scrape_error')} if job.get('detail_scrape_error') else None,

                # Set enrichment status to pending (ready for AI enrichment)
                enrichment_status='pending' if job.get('detail_scrape_success') else None,
            )

            db.add(golden_job)
            db.commit()
            logger.info(f"[Detail Scrape Activity] ✅ Created new golden record for {posting_url}")

        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[Detail Scrape Activity] ❌ Failed to save job: {str(e)}")
        raise
    finally:
        db.close()


@activity.defn
async def publish_detail_scraped_jobs(jobs: List[Dict[str, Any]]) -> int:
    """
    Publish detail-scraped jobs to the queue for downstream processing.

    Args:
        jobs: List of job dictionaries with scraped details

    Returns:
        Number of jobs published
    """
    try:
        channel = await get_rabbitmq_channel()
        exchange = await channel.get_exchange(DETAIL_SCRAPED_JOBS_EXCHANGE)

        published_count = 0

        logger.info(f"[Detail Scrape Activity] 📤 Publishing {len(jobs)} jobs to {DETAIL_SCRAPED_JOBS_QUEUE} queue")

        for idx, job in enumerate(jobs, 1):
            # Only publish successfully scraped jobs
            if not job.get('detail_scrape_success'):
                continue

            message = Message(
                body=json.dumps(job).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={
                    "source_job_id": job.get('id'),
                    "posting_url": job.get('posting_url'),
                    "scraper_source": job.get('scraper_source', 'unknown')
                }
            )

            await exchange.publish(message, routing_key=DETAIL_SCRAPED_JOBS_QUEUE)
            published_count += 1

            if idx % 50 == 0:
                logger.info(f"[Detail Scrape Activity] Published {published_count}/{len(jobs)} jobs to queue")

        logger.info(f"[Detail Scrape Activity] ✅ Published {published_count} jobs to {DETAIL_SCRAPED_JOBS_QUEUE} queue")

        return published_count

    except Exception as e:
        logger.error(f"[Detail Scrape Activity] ❌ Failed to publish jobs to queue: {str(e)}")
        raise


@activity.defn
async def get_detail_scrape_stats() -> Dict[str, Any]:
    """
    Get statistics about detail scraping progress.

    Returns:
        Dictionary with scraping stats
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

        return {
            'total_raw_jobs': total_raw,
            'total_golden_jobs': total_golden,
            'detail_scraped': detail_scraped,
            'detail_failed': detail_failed,
            'pending_enrichment': pending_enrichment,
            'enriched': enriched,
            'not_yet_processed': total_raw - total_golden
        }

    except Exception as e:
        logger.error(f"[Detail Scrape Activity] ❌ Failed to get stats: {str(e)}")
        raise
    finally:
        db.close()
