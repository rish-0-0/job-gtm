from temporalio import activity
from typing import Dict, Any, List
import httpx
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
from models.job_listing import JobListing
from datetime import datetime, timezone

SCRAPER_URL = os.getenv("SCRAPER_URL", "http://scraper:6000")

@activity.defn
async def get_available_scrapers() -> List[str]:
    """
    Activity to get all available scrapers from the scraper service

    Returns:
        List of available scraper names
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{SCRAPER_URL}/scrapers")
            response.raise_for_status()
            data = response.json()
            scrapers = data.get("scrapers", [])
            activity.logger.info(f"Found {len(scrapers)} available scrapers: {scrapers}")
            return scrapers
    except Exception as e:
        activity.logger.error(f"Failed to get available scrapers: {str(e)}")
        raise

@activity.defn
async def call_scraper_service(scraper: str, page: int) -> List[Dict[str, Any]]:
    """
    Activity to call the scraper service

    Args:
        scraper: Name of the scraper
        page: Page number to scrape

    Returns:
        List of job listings
    """
    try:
        activity.logger.info(f"Calling scraper service: {scraper}, page {page}")
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{SCRAPER_URL}/scrape",
                json={"scraper": scraper, "params": {"page": page}}
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("result", [])
            activity.logger.info(f"Scraped {len(results)} jobs from {scraper}, page {page}")
            return results
    except Exception as e:
        activity.logger.error(f"Failed to scrape {scraper} page {page}: {str(e)}")
        raise

@activity.defn
async def store_scrape_results(scraper: str, results: List[Dict[str, Any]]) -> int:
    """
    Activity to store scraping results in the database

    Args:
        scraper: Name of the scraper (source)
        results: List of job listings to store

    Returns:
        Number of jobs stored (excluding duplicates)
    """
    db: Session = SessionLocal()
    stored_count = 0
    duplicate_count = 0

    try:
        activity.logger.info(f"Storing {len(results)} job listings from {scraper}")

        for job_data in results:
            try:
                # Note: scraper returns camelCase fields (e.g., postingUrl)
                posting_url = job_data.get("postingUrl")

                # Create new job listing
                # Map camelCase fields from scraper to snake_case fields in database
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
                    posting_url=posting_url,
                    hiring_team=job_data.get("hiringTeam"),
                    about_company=job_data.get("aboutCompany"),
                    scraper_source=scraper,
                    scraped_at=datetime.now(timezone.utc)
                )

                db.add(job_listing)
                db.flush()  # Flush to catch IntegrityError immediately
                stored_count += 1
                activity.logger.info(
                    f"Inserted new job listing: {job_data.get('companyTitle')} - "
                    f"{job_data.get('jobRole')} ({posting_url})"
                )

            except IntegrityError:
                # Handle unique constraint violation (duplicate job listing)
                db.rollback()
                activity.logger.debug(f"Duplicate job listing skipped: {posting_url}")
                duplicate_count += 1
                continue

        db.commit()
        activity.logger.info(
            f"Successfully stored {stored_count} new job listings from {scraper} "
            f"({duplicate_count} duplicates skipped)"
        )
        return stored_count

    except Exception as e:
        db.rollback()
        activity.logger.error(f"Failed to store scrape results: {str(e)}")
        raise
    finally:
        db.close()
