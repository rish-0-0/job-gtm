from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Dict, Any
import asyncio
from const import MAX_PAGES, CONCURRENT_PAGES_PER_SCRAPER, BATCH_DELAY_SECONDS

@workflow.defn
class ScrapeWorkflow:
    """
    Workflow for orchestrating web scraping jobs across all available scrapers
    """

    @workflow.run
    async def run(self, max_pages: int = MAX_PAGES, scraper_name: str = None) -> Dict[str, Any]:
        """
        Execute the scraping workflow for all or a specific scraper

        Args:
            max_pages: Maximum number of pages to scrape per scraper (default: MAX_PAGES)
            scraper_name: Optional - name of specific scraper to run (e.g., 'dice', 'simplyhired')
                         If None, runs all available scrapers

        Returns:
            Summary of scraping results
        """
        workflow.logger.info(f"Starting scrape workflow with max_pages={max_pages}, scraper={scraper_name or 'all'}")

        # Step 1: Get scrapers to process
        if scraper_name:
            # Single scraper mode
            scrapers = [scraper_name]
            workflow.logger.info(f"Running single scraper: {scraper_name}")
        else:
            # All scrapers mode
            scrapers = await workflow.execute_activity(
                "get_available_scrapers",
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    maximum_attempts=3
                )
            )
            workflow.logger.info(f"Found {len(scrapers)} scrapers: {scrapers}")

        # Summary of results
        summary = {
            "total_scrapers": len(scrapers),
            "scrapers_processed": [],
            "total_jobs_stored": 0,
            "max_pages": max_pages
        }

        # Step 2: Process each scraper concurrently
        scraper_tasks = []
        for scraper_name in scrapers:
            task = self._scrape_all_pages(scraper_name, max_pages)
            scraper_tasks.append(task)

        # Wait for all scrapers to complete
        results = await asyncio.gather(*scraper_tasks, return_exceptions=True)

        # Process results
        for idx, result in enumerate(results):
            scraper_name = scrapers[idx]
            if isinstance(result, Exception):
                workflow.logger.error(f"Scraper {scraper_name} failed: {str(result)}")
                summary["scrapers_processed"].append({
                    "scraper": scraper_name,
                    "status": "failed",
                    "error": str(result)
                })
            else:
                workflow.logger.info(f"Scraper {scraper_name} completed: {result}")
                summary["scrapers_processed"].append(result)
                summary["total_jobs_stored"] += result.get("total_jobs_stored", 0)

        workflow.logger.info(f"Scrape workflow completed. Total jobs published to queue: {summary['total_jobs_stored']}")

        return summary

    async def _scrape_all_pages(self, scraper_name: str, max_pages: int) -> Dict[str, Any]:
        """
        Scrape all pages for a specific scraper in parallel batches to avoid DDoS detection

        Args:
            scraper_name: Name of the scraper
            max_pages: Maximum number of pages to scrape

        Returns:
            Summary of scraping results for this scraper
        """
        scraper_summary = {
            "scraper": scraper_name,
            "status": "completed",
            "pages_scraped": 0,
            "total_jobs_stored": 0
        }

        workflow.logger.info(
            f"Starting batched parallel scraping of {max_pages} pages for {scraper_name} "
            f"({CONCURRENT_PAGES_PER_SCRAPER} concurrent requests per batch, "
            f"{BATCH_DELAY_SECONDS}s delay between batches)"
        )

        # Step 3: Process pages in batches to avoid DDoS detection
        all_page_results = []

        for batch_start in range(1, max_pages + 1, CONCURRENT_PAGES_PER_SCRAPER):
            batch_end = min(batch_start + CONCURRENT_PAGES_PER_SCRAPER, max_pages + 1)
            batch_pages = list(range(batch_start, batch_end))

            workflow.logger.info(f"Starting batch: pages {batch_start}-{batch_end-1} for {scraper_name}")

            # Launch this batch of pages in parallel
            batch_tasks = [self._scrape_single_page(scraper_name, page) for page in batch_pages]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            all_page_results.extend(batch_results)

            # Add delay between batches (except after the last batch)
            if batch_end <= max_pages:
                workflow.logger.info(f"Waiting {BATCH_DELAY_SECONDS}s before next batch to avoid rate limiting")
                await asyncio.sleep(BATCH_DELAY_SECONDS)

        # Step 4: Process results from all pages
        successful_pages = 0
        failed_pages = 0

        for page_num, result in enumerate(all_page_results, start=1):
            if isinstance(result, Exception):
                workflow.logger.error(f"Page {page_num} of {scraper_name} failed: {str(result)}")
                failed_pages += 1
            elif result is not None:
                stored_count = result.get("stored_count", 0)
                scraper_summary["total_jobs_stored"] += stored_count
                successful_pages += 1
                if stored_count > 0:
                    workflow.logger.info(f"Page {page_num} of {scraper_name}: stored {stored_count} jobs")

        scraper_summary["pages_scraped"] = successful_pages

        if failed_pages > 0:
            scraper_summary["status"] = "partial"
            scraper_summary["failed_pages"] = failed_pages
            workflow.logger.warning(f"{scraper_name} completed with {failed_pages} failed pages")
        else:
            workflow.logger.info(f"{scraper_name} completed successfully: {successful_pages} pages, {scraper_summary['total_jobs_stored']} jobs stored")

        return scraper_summary

    async def _scrape_single_page(self, scraper_name: str, page: int) -> Dict[str, Any]:
        """
        Scrape a single page and publish results to queue

        Args:
            scraper_name: Name of the scraper
            page: Page number to scrape

        Returns:
            Dictionary with published_count
        """
        try:
            # Call scraper service to get jobs
            results = await workflow.execute_activity(
                "call_scraper_service",
                args=[scraper_name, page],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )

            # Publish results to queue if we got any
            if results:
                published_count = await workflow.execute_activity(
                    "publish_scrape_results",
                    args=[scraper_name, results],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(seconds=10),
                        maximum_attempts=5
                    )
                )
                return {"stored_count": published_count}
            else:
                # Empty page - this is normal, just return 0
                return {"stored_count": 0}

        except Exception as e:
            workflow.logger.error(f"Error scraping {scraper_name}, page {page}: {str(e)}")
            raise
