"""
Temporal workflows for detail scraping job URLs.

Uses a parent-child workflow pattern to avoid exceeding Temporal's history event limit.
- DetailScrapeCoordinatorWorkflow: Parent that spawns child workflows for each chunk
- DetailScrapeChunkWorkflow: Child that processes a single chunk of jobs
"""
import asyncio
from datetime import timedelta
from typing import Dict, Any, List
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import logging
    logger = logging.getLogger(__name__)


@workflow.defn
class DetailScrapeChunkWorkflow:
    """
    Child workflow that processes a single chunk of jobs.
    Each chunk workflow has its own history, avoiding the event limit.
    """

    @workflow.run
    async def run(
        self,
        chunk_index: int,
        offset: int,
        limit: int,
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Process a single chunk of jobs.

        Args:
            chunk_index: Index of this chunk (for logging)
            offset: DB offset to fetch jobs from
            limit: Number of jobs in this chunk
            max_concurrent: Max concurrent scrape operations

        Returns:
            Summary of chunk processing
        """
        workflow.logger.info(
            f"[Chunk {chunk_index}] Starting chunk workflow: offset={offset}, limit={limit}"
        )

        # Step 1: Fetch this chunk of jobs
        jobs = await workflow.execute_activity(
            "fetch_jobs_chunk",
            args=[offset, limit],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
            )
        )

        if not jobs:
            workflow.logger.info(f"[Chunk {chunk_index}] No jobs in chunk, skipping")
            return {
                "chunk_index": chunk_index,
                "total_jobs": 0,
                "success": 0,
                "failed": 0,
                "status": "empty"
            }

        workflow.logger.info(f"[Chunk {chunk_index}] Processing {len(jobs)} jobs")

        # Step 2: Process jobs with concurrency control
        total_success = 0
        total_failed = 0

        for i in range(0, len(jobs), max_concurrent):
            concurrent_batch = jobs[i:i + max_concurrent]

            workflow.logger.info(
                f"[Chunk {chunk_index}] Scraping batch {i//max_concurrent + 1}: "
                f"{len(concurrent_batch)} jobs concurrently"
            )

            # Scrape jobs concurrently
            scrape_tasks = []
            for job in concurrent_batch:
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

            # Wait for all concurrent scrapes
            results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

            # Process results
            successful_scrapes = []
            for result in results:
                if isinstance(result, Exception):
                    workflow.logger.error(f"[Chunk {chunk_index}] Scrape failed: {str(result)}")
                    total_failed += 1
                    continue

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
                        successful_scrapes.append(result)
                        total_success += 1
                    else:
                        total_failed += 1

                except Exception as e:
                    workflow.logger.error(f"[Chunk {chunk_index}] Save failed: {str(e)}")
                    total_failed += 1

            # Publish successful scrapes to queue
            if successful_scrapes:
                try:
                    await workflow.execute_activity(
                        "publish_detail_scraped_jobs",
                        args=[successful_scrapes],
                        start_to_close_timeout=timedelta(seconds=60),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            initial_interval=timedelta(seconds=1),
                            maximum_interval=timedelta(seconds=10),
                        )
                    )
                except Exception as e:
                    workflow.logger.error(f"[Chunk {chunk_index}] Publish failed: {str(e)}")

            # Small delay between batches
            await asyncio.sleep(0.5)

        workflow.logger.info(
            f"[Chunk {chunk_index}] ✅ Completed: success={total_success}, failed={total_failed}"
        )

        return {
            "chunk_index": chunk_index,
            "total_jobs": len(jobs),
            "success": total_success,
            "failed": total_failed,
            "status": "completed"
        }


@workflow.defn
class DetailScrapeWorkflow:
    """
    Coordinator workflow that spawns child workflows for each chunk.

    This is the main entry point. It:
    1. Gets chunk info (lightweight - just counts)
    2. Spawns a child workflow for each chunk
    3. Waits for all children to complete
    4. Aggregates results

    By using child workflows, each chunk has its own history,
    avoiding Temporal's history event limit (~50k events).
    """

    @workflow.run
    async def run(
        self,
        chunk_size: int = 50,
        max_concurrent_chunks: int = 3,
        max_concurrent_per_chunk: int = 5
    ) -> Dict[str, Any]:
        """
        Execute detail scraping with chunked child workflows.

        Args:
            chunk_size: Number of jobs per chunk/child workflow
            max_concurrent_chunks: How many child workflows to run in parallel
            max_concurrent_per_chunk: Concurrent scrapes within each chunk

        Returns:
            Aggregated summary
        """
        workflow.logger.info(
            f"[Coordinator] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Coordinator] 🚀 Starting detail scrape coordinator"
        )
        workflow.logger.info(
            f"[Coordinator] Config: chunk_size={chunk_size}, "
            f"max_concurrent_chunks={max_concurrent_chunks}"
        )
        workflow.logger.info(
            f"[Coordinator] ════════════════════════════════════════"
        )

        # Step 1: Get chunk info
        chunk_info = await workflow.execute_activity(
            "get_jobs_chunk_info",
            args=[chunk_size],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
            )
        )

        total_jobs = chunk_info['total_jobs']
        chunks = chunk_info['chunks']

        workflow.logger.info(
            f"[Coordinator] 📊 Found {total_jobs} jobs in {len(chunks)} chunks"
        )

        if total_jobs == 0:
            return {
                "total_jobs": 0,
                "total_chunks": 0,
                "success": 0,
                "failed": 0,
                "status": "completed",
                "message": "No jobs to process"
            }

        # Step 2: Spawn child workflows in batches
        all_results = []

        for i in range(0, len(chunks), max_concurrent_chunks):
            batch_chunks = chunks[i:i + max_concurrent_chunks]

            workflow.logger.info(
                f"[Coordinator] 🔄 Spawning {len(batch_chunks)} child workflows "
                f"(batch {i//max_concurrent_chunks + 1})"
            )

            # Start child workflows concurrently
            child_handles = []
            for chunk in batch_chunks:
                handle = await workflow.start_child_workflow(
                    DetailScrapeChunkWorkflow.run,
                    args=[
                        chunk['chunk_index'],
                        chunk['offset'],
                        chunk['limit'],
                        max_concurrent_per_chunk
                    ],
                    id=f"{workflow.info().workflow_id}-chunk-{chunk['chunk_index']}",
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=5),
                        maximum_interval=timedelta(seconds=30),
                    )
                )
                child_handles.append(handle)

            # Wait for all child workflows in this batch
            for handle in child_handles:
                try:
                    result = await handle
                    all_results.append(result)
                    workflow.logger.info(
                        f"[Coordinator] ✅ Chunk {result['chunk_index']} completed: "
                        f"success={result['success']}, failed={result['failed']}"
                    )
                except Exception as e:
                    workflow.logger.error(f"[Coordinator] ❌ Child workflow failed: {str(e)}")
                    all_results.append({
                        "chunk_index": -1,
                        "total_jobs": 0,
                        "success": 0,
                        "failed": 0,
                        "status": "failed",
                        "error": str(e)
                    })

        # Step 3: Aggregate results
        total_success = sum(r.get('success', 0) for r in all_results)
        total_failed = sum(r.get('failed', 0) for r in all_results)
        chunks_completed = sum(1 for r in all_results if r.get('status') == 'completed')

        workflow.logger.info(
            f"[Coordinator] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Coordinator] 🎉 All chunks completed!"
        )
        workflow.logger.info(
            f"[Coordinator] Total: {total_jobs} jobs, "
            f"Success: {total_success}, Failed: {total_failed}"
        )
        workflow.logger.info(
            f"[Coordinator] Chunks: {chunks_completed}/{len(chunks)} completed"
        )
        workflow.logger.info(
            f"[Coordinator] ════════════════════════════════════════"
        )

        return {
            "total_jobs": total_jobs,
            "total_chunks": len(chunks),
            "chunks_completed": chunks_completed,
            "success": total_success,
            "failed": total_failed,
            "status": "completed" if total_failed == 0 else "completed_with_errors",
            "message": f"Processed {total_success + total_failed} jobs across {len(chunks)} chunks"
        }
