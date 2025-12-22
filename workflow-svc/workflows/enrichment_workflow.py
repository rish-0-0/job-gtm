"""
Temporal workflow for job listing enrichment
Uses chunked fetching to avoid Temporal gRPC message size limits.
"""
import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class EnrichmentWorkflow:
    """
    Workflow to enrich all existing job listings with AI-powered insights.
    Uses chunked fetching to keep message sizes under Temporal's 4MB limit.
    """

    @workflow.run
    async def run(
        self,
        chunk_size: int = 50,
        batch_size: int = 100,
        skip_already_enriched: bool = True
    ) -> Dict[str, Any]:
        """
        Execute enrichment workflow:
        1. Get chunk info (count and offsets only - small payload)
        2. For each chunk, fetch jobs and publish to queue
        3. Track progress

        Args:
            chunk_size: Number of jobs to fetch per chunk (keeps gRPC messages small)
            batch_size: Number of jobs to publish per RabbitMQ batch
            skip_already_enriched: Skip jobs already enriched

        Returns:
            Summary of workflow execution
        """
        workflow.logger.info(
            f"[Enrichment Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Enrichment Workflow] Starting enrichment workflow"
        )
        workflow.logger.info(
            f"[Enrichment Workflow] Config: chunk_size={chunk_size}, batch_size={batch_size}, "
            f"skip_already_enriched={skip_already_enriched}"
        )
        workflow.logger.info(
            f"[Enrichment Workflow] ════════════════════════════════════════"
        )

        # Step 1: Get chunk info (lightweight - just counts and offsets)
        chunk_info = await workflow.execute_activity(
            "get_enrichment_chunk_info",
            args=[chunk_size, skip_already_enriched],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
            )
        )

        total_jobs = chunk_info['total_jobs']
        chunks = chunk_info['chunks']

        workflow.logger.info(f"[Enrichment Workflow] 📊 Found {total_jobs} jobs in {len(chunks)} chunks")

        if total_jobs == 0:
            workflow.logger.info(f"[Enrichment Workflow] ⚠️ No jobs to enrich, exiting")
            return {
                "total_jobs": 0,
                "published_to_queue": 0,
                "chunk_size": chunk_size,
                "batch_size": batch_size,
                "status": "completed",
                "message": "No jobs to enrich"
            }

        # Step 2: Process each chunk - fetch and publish
        total_published = 0
        chunks_processed = 0

        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            offset = chunk['offset']
            limit = chunk['limit']

            workflow.logger.info(
                f"[Enrichment Workflow] 📥 Fetching chunk {chunk_index + 1}/{len(chunks)} "
                f"(offset={offset}, limit={limit})"
            )

            # Fetch this chunk of jobs
            try:
                jobs = await workflow.execute_activity(
                    "fetch_enrichment_chunk",
                    args=[offset, limit, skip_already_enriched],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        maximum_attempts=3,
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(seconds=10),
                    )
                )
            except Exception as e:
                workflow.logger.error(
                    f"[Enrichment Workflow] ❌ Failed to fetch chunk {chunk_index + 1}: {str(e)}"
                )
                continue

            # Publish jobs from this chunk in batches
            chunk_published = 0
            for i in range(0, len(jobs), batch_size):
                batch = jobs[i:i + batch_size]

                try:
                    published = await workflow.execute_activity(
                        "publish_to_raw_jobs_queue",
                        args=[batch],
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            initial_interval=timedelta(seconds=1),
                            maximum_interval=timedelta(seconds=10),
                        )
                    )
                    chunk_published += published
                except Exception as e:
                    workflow.logger.error(
                        f"[Enrichment Workflow] ❌ Failed to publish batch in chunk {chunk_index + 1}: {str(e)}"
                    )
                    continue

            total_published += chunk_published
            chunks_processed += 1

            workflow.logger.info(
                f"[Enrichment Workflow] ✅ Chunk {chunk_index + 1}/{len(chunks)} done: "
                f"{chunk_published} published (total: {total_published}/{total_jobs} = {total_published/total_jobs*100:.1f}%)"
            )

            # Small delay between chunks
            await asyncio.sleep(0.2)

        workflow.logger.info(
            f"[Enrichment Workflow] ════════════════════════════════════════"
        )
        workflow.logger.info(
            f"[Enrichment Workflow] 🎉 Workflow completed: "
            f"{total_published}/{total_jobs} jobs published ({total_published/total_jobs*100:.1f}%)"
        )
        workflow.logger.info(
            f"[Enrichment Workflow] ════════════════════════════════════════"
        )

        return {
            "total_jobs": total_jobs,
            "published_to_queue": total_published,
            "chunks_processed": chunks_processed,
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "batch_size": batch_size,
            "status": "completed" if total_published == total_jobs else "partial",
            "message": f"Published {total_published} out of {total_jobs} jobs"
        }
