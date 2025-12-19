"""
Temporal workflow for job listing enrichment
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
    Workflow to enrich all existing job listings with AI-powered insights
    """

    @workflow.run
    async def run(
        self,
        batch_size: int = 100,
        skip_already_enriched: bool = True
    ) -> Dict[str, Any]:
        """
        Execute enrichment workflow:
        1. Fetch jobs from job_listings table
        2. Filter out already enriched (if skip_already_enriched)
        3. Publish to raw_jobs_for_processing queue in batches
        4. Track progress

        Args:
            batch_size: Number of jobs to publish per batch
            skip_already_enriched: Skip jobs already in golden table

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
            f"[Enrichment Workflow] Config: batch_size={batch_size}, "
            f"skip_already_enriched={skip_already_enriched}"
        )
        workflow.logger.info(
            f"[Enrichment Workflow] ════════════════════════════════════════"
        )

        # Step 1: Fetch all jobs to enrich
        jobs_to_enrich = await workflow.execute_activity(
            "fetch_jobs_for_enrichment",
            args=[skip_already_enriched],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
            )
        )

        total_jobs = len(jobs_to_enrich)
        workflow.logger.info(f"[Enrichment Workflow] 📊 Found {total_jobs} jobs to enrich")

        if total_jobs == 0:
            workflow.logger.info(f"[Enrichment Workflow] ⚠️ No jobs to enrich, exiting")
            return {
                "total_jobs": 0,
                "published_to_queue": 0,
                "batch_size": batch_size,
                "status": "completed",
                "message": "No jobs to enrich"
            }

        # Step 2: Publish to raw_jobs_for_processing in batches
        total_published = 0
        batch_count = 0

        for i in range(0, total_jobs, batch_size):
            batch = jobs_to_enrich[i:i + batch_size]
            batch_count += 1

            workflow.logger.info(
                f"[Enrichment Workflow] 📤 Publishing batch {batch_count}/{(total_jobs + batch_size - 1) // batch_size} "
                f"({len(batch)} jobs, {i+len(batch)}/{total_jobs} total)"
            )

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

                total_published += published
                workflow.logger.info(
                    f"[Enrichment Workflow] ✅ Batch {batch_count} published: {published} jobs "
                    f"(total progress: {total_published}/{total_jobs} = {total_published/total_jobs*100:.1f}%)"
                )

            except Exception as e:
                workflow.logger.error(
                    f"[Enrichment Workflow] ❌ Failed to publish batch {batch_count}: {str(e)}"
                )
                # Continue with next batch even if one fails
                continue

            # Small delay between batches to avoid overwhelming queue
            await asyncio.sleep(0.5)

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
            "batch_count": batch_count,
            "batch_size": batch_size,
            "status": "completed" if total_published == total_jobs else "partial",
            "message": f"Published {total_published} out of {total_jobs} jobs"
        }
