from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Dict, Any
import asyncio
from const import MAX_PAGES

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

        workflow.logger.info(f"Scrape workflow completed. Total jobs stored: {summary['total_jobs_stored']}")

        # Step 5: Future enhancement - raise message queue event
        # TODO: Add message queue notification for downstream processing

        return summary

    async def _scrape_all_pages(self, scraper_name: str, max_pages: int) -> Dict[str, Any]:
        """
        Scrape all pages for a specific scraper

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

        # Step 3 & 4: Loop through pages, scraping and storing results
        for page in range(1, max_pages + 1):
            try:
                workflow.logger.info(f"Scraping {scraper_name}, page {page}")

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

                # Store results in database
                if results:
                    stored_count = await workflow.execute_activity(
                        "store_scrape_results",
                        args=[scraper_name, results],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(
                            initial_interval=timedelta(seconds=2),
                            maximum_interval=timedelta(seconds=10),
                            maximum_attempts=5
                        )
                    )

                    scraper_summary["total_jobs_stored"] += stored_count
                    workflow.logger.info(f"Stored {stored_count} jobs from {scraper_name}, page {page}")
                else:
                    workflow.logger.info(f"No results from {scraper_name}, page {page}. Stopping pagination.")
                    break  # Stop scraping this scraper when we get 0 results

                scraper_summary["pages_scraped"] = page

            except Exception as e:
                workflow.logger.error(f"Error scraping {scraper_name}, page {page}: {str(e)}")
                scraper_summary["status"] = "partial"
                scraper_summary["last_error"] = str(e)
                break

        return scraper_summary
