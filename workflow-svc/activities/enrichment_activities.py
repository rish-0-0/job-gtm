"""
Temporal activities for job listing enrichment workflow
"""
import json
import logging
from typing import List, Dict, Any
from temporalio import activity
from aio_pika import Message, DeliveryMode

from database import SessionLocal
from models import JobListing, JobListingGolden
from queue_config import get_rabbitmq_channel, RAW_JOBS_QUEUE, RAW_JOBS_EXCHANGE

logger = logging.getLogger(__name__)


@activity.defn
async def fetch_jobs_for_enrichment(skip_already_enriched: bool = True) -> List[Dict[str, Any]]:
    """
    Fetch jobs from job_listings_golden that need AI enrichment.

    Jobs must have:
    - detail_scrape_status = 'completed' (Phase 1 done)
    - enrichment_status = 'pending' or NULL (Phase 2 not done)

    Args:
        skip_already_enriched: If True, only fetch jobs with enrichment_status='pending'

    Returns:
        List of job dictionaries with full scraped details
    """
    db = SessionLocal()
    try:
        logger.info("[Enrichment Activity] Fetching detail-scraped jobs for AI enrichment...")

        # Query golden table for jobs that are detail-scraped but not yet AI-enriched
        query = db.query(JobListingGolden).filter(
            JobListingGolden.detail_scrape_status == 'completed'
        )

        if skip_already_enriched:
            query = query.filter(
                (JobListingGolden.enrichment_status == 'pending') |
                (JobListingGolden.enrichment_status.is_(None))
            )

        jobs = query.all()

        logger.info(f"[Enrichment Activity] Found {len(jobs)} detail-scraped jobs to enrich")

        # Convert to dictionaries with full scraped details
        result = []
        for idx, job in enumerate(jobs, 1):
            if idx % 100 == 0:
                logger.info(f"[Enrichment Activity] Converted {idx}/{len(jobs)} jobs to dictionaries")
            result.append({
                'id': job.id,
                'source_job_id': job.source_job_id,
                'posting_url': job.posting_url,
                'company_title': job.company_title,
                'job_role': job.job_role,
                'job_location': job.job_location_raw,
                'employment_type': job.employment_type_raw,
                'salary_range': job.salary_range_raw,
                'min_salary': float(job.min_salary_raw) if job.min_salary_raw else None,
                'max_salary': float(job.max_salary_raw) if job.max_salary_raw else None,
                'required_experience': job.required_experience,
                'seniority_level': job.seniority_level_raw,
                # Full job description from Phase 1 detail scraping - AI will extract all details
                'job_description_full': job.job_description_full,
                'about_company': job.about_company_raw,
                'hiring_team': job.hiring_team_raw,
                # Metadata
                'date_posted': job.date_posted,
                'scraper_source': job.scraper_source,
                'scraped_at': job.scraped_at.isoformat() if job.scraped_at else None,
                'detail_scraped_at': job.detail_scraped_at.isoformat() if job.detail_scraped_at else None,
            })

        logger.info(f"[Enrichment Activity] ✅ Successfully prepared {len(result)} jobs for AI enrichment")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch jobs for enrichment: {str(e)}")
        raise
    finally:
        db.close()


@activity.defn
async def publish_to_raw_jobs_queue(jobs: List[Dict[str, Any]]) -> int:
    """
    Publish jobs to raw_jobs_for_processing queue

    Args:
        jobs: List of job dictionaries

    Returns:
        Number of jobs published
    """
    try:
        channel = await get_rabbitmq_channel()
        exchange = await channel.get_exchange(RAW_JOBS_EXCHANGE)

        published_count = 0

        logger.info(f"[Enrichment Activity] Publishing {len(jobs)} jobs to {RAW_JOBS_QUEUE} queue")

        for idx, job in enumerate(jobs, 1):
            message = Message(
                body=json.dumps(job).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={
                    "source_job_id": job['id'],
                    "posting_url": job['posting_url'],
                    "scraper_source": job.get('scraper_source', 'unknown')
                }
            )

            await exchange.publish(message, routing_key=RAW_JOBS_QUEUE)
            published_count += 1

            if idx % 50 == 0:
                logger.info(f"[Enrichment Activity] Published {idx}/{len(jobs)} jobs to queue")

        logger.info(f"[Enrichment Activity] ✅ Published {published_count} jobs to {RAW_JOBS_QUEUE} queue")

        return published_count

    except Exception as e:
        logger.error(f"Failed to publish jobs to queue: {str(e)}")
        raise
