"""
Temporal workflow for detail scraping job URLs
"""
import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class DetailScrapeWorkflow:
    """
    Workflow to scrape full details from job posting URLs.

    This is Phase 1 of the enrichment pipeline:
    1. Fetch jobs from job_listings that need detail scraping
    2. For each job, call the scraper service to get full page details
    3. Save the scraped details to job_listings_golden
    4. Mark jobs as ready for AI enrichment (Phase 2)
    """

    @workflow.run
    async def run(
        self,
        batch_size: int = 10,
        max_concurrent: int = 5,
        skip_already_scraped: bool = True,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute detail scraping workflow.

        Args:
            batch_size: Number of jobs to process per batch
            max_concurrent: Maximum concurrent scraping operations
            skip_already_scraped: Skip jobs already detail-scraped
            limit: Maximum total jobs to process (None = all)

        Returns:
            Summary of workflow execution
        """
        workflow.logger.info(
            f"[Detail Scrape Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Detail Scrape Workflow] 🚀 Starting detail scraping workflow"
        )
        workflow.logger.info(
            f"[Detail Scrape Workflow] Config: batch_size={batch_size}, "
            f"max_concurrent={max_concurrent}, skip_already_scraped={skip_already_scraped}, "
            f"limit={limit}"
        )
        workflow.logger.info(
            f"[Detail Scrape Workflow] ════════════════════════════════════════"
        )

        # Step 1: Fetch all jobs to scrape
        jobs_to_scrape = await workflow.execute_activity(
            "fetch_jobs_for_detail_scraping",
            args=[skip_already_scraped, limit],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
            )
        )

        total_jobs = len(jobs_to_scrape)
        workflow.logger.info(f"[Detail Scrape Workflow] 📊 Found {total_jobs} jobs to detail-scrape")

        if total_jobs == 0:
            workflow.logger.info(f"[Detail Scrape Workflow] ⚠️ No jobs to scrape, exiting")
            return {
                "total_jobs": 0,
                "scraped_success": 0,
                "scraped_failed": 0,
                "status": "completed",
                "message": "No jobs to detail-scrape"
            }

        # Step 2: Process jobs in batches with concurrency control
        total_success = 0
        total_failed = 0
        batch_count = 0

        for i in range(0, total_jobs, batch_size):
            batch = jobs_to_scrape[i:i + batch_size]
            batch_count += 1
            batch_start = i + 1
            batch_end = min(i + batch_size, total_jobs)

            workflow.logger.info(
                f"[Detail Scrape Workflow] 📦 Processing batch {batch_count} "
                f"(jobs {batch_start}-{batch_end} of {total_jobs})"
            )

            # Process batch with concurrency limit
            # We use a semaphore pattern by chunking within the batch
            batch_results = []

            for j in range(0, len(batch), max_concurrent):
                concurrent_chunk = batch[j:j + max_concurrent]

                workflow.logger.info(
                    f"[Detail Scrape Workflow] 🔄 Scraping {len(concurrent_chunk)} jobs concurrently..."
                )

                # Scrape jobs concurrently
                scrape_tasks = []
                for job in concurrent_chunk:
                    scrape_tasks.append(
                        workflow.execute_activity(
                            "scrape_job_details",
                            args=[job],
                            start_to_close_timeout=timedelta(minutes=2),
                            retry_policy=RetryPolicy(
                                maximum_attempts=2,
                                initial_interval=timedelta(seconds=2),
                                maximum_interval=timedelta(seconds=10),
                            )
                        )
                    )

                # Wait for all concurrent scrapes to complete
                chunk_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

                # Process results and save to golden table
                for result in chunk_results:
                    if isinstance(result, Exception):
                        workflow.logger.error(
                            f"[Detail Scrape Workflow] ❌ Scrape activity failed: {str(result)}"
                        )
                        total_failed += 1
                        continue

                    batch_results.append(result)

                    # Save to golden table
                    try:
                        await workflow.execute_activity(
                            "save_detail_scraped_job",
                            args=[result],
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=RetryPolicy(
                                maximum_attempts=3,
                                initial_interval=timedelta(seconds=1),
                                maximum_interval=timedelta(seconds=5),
                            )
                        )

                        if result.get('detail_scrape_success'):
                            total_success += 1
                        else:
                            total_failed += 1

                    except Exception as e:
                        workflow.logger.error(
                            f"[Detail Scrape Workflow] ❌ Failed to save job: {str(e)}"
                        )
                        total_failed += 1

                # Small delay between concurrent chunks to avoid overwhelming the scraper
                await asyncio.sleep(1)

            # Log batch progress
            progress = (total_success + total_failed) / total_jobs * 100
            workflow.logger.info(
                f"[Detail Scrape Workflow] ✅ Batch {batch_count} complete: "
                f"success={total_success}, failed={total_failed}, "
                f"progress={progress:.1f}%"
            )

            # Delay between batches
            await asyncio.sleep(2)

        # Final summary
        workflow.logger.info(
            f"[Detail Scrape Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Detail Scrape Workflow] 🎉 Workflow completed!"
        )
        workflow.logger.info(
            f"[Detail Scrape Workflow] Total: {total_jobs}, "
            f"Success: {total_success}, Failed: {total_failed}"
        )
        workflow.logger.info(
            f"[Detail Scrape Workflow] ════════════════════════════════════════"
        )

        return {
            "total_jobs": total_jobs,
            "scraped_success": total_success,
            "scraped_failed": total_failed,
            "batch_count": batch_count,
            "status": "completed" if total_failed == 0 else "completed_with_errors",
            "message": f"Scraped {total_success} jobs successfully, {total_failed} failed"
        }
