"""
RabbitMQ activities for publishing scraped job listings
"""
from temporalio import activity
from typing import Dict, Any, List
import json
from aio_pika import Message, DeliveryMode
from queue_config import get_rabbitmq_channel, JOBS_EXCHANGE, JOBS_QUEUE


@activity.defn
async def publish_scrape_results(scraper: str, results: List[Dict[str, Any]]) -> int:
    """
    Activity to publish scraping results to RabbitMQ queue

    Args:
        scraper: Name of the scraper (source)
        results: List of job listings to publish

    Returns:
        Number of messages published to queue
    """
    try:
        activity.logger.info(f"Publishing {len(results)} job listings from {scraper} to queue")

        channel = await get_rabbitmq_channel()
        exchange = await channel.get_exchange(JOBS_EXCHANGE)

        published_count = 0

        for job_data in results:
            # Add scraper source to the message
            message_data = {
                **job_data,
                "scraper_source": scraper
            }

            # Create persistent message
            message = Message(
                body=json.dumps(message_data).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,  # Survive broker restart
                content_type="application/json",
                headers={
                    "scraper": scraper,
                    "posting_url": job_data.get("postingUrl", "")
                }
            )

            # Publish to exchange
            await exchange.publish(
                message,
                routing_key=JOBS_QUEUE
            )
            published_count += 1

        activity.logger.info(
            f"Successfully published {published_count} job listings from {scraper} to queue"
        )
        return published_count

    except Exception as e:
        activity.logger.error(f"Failed to publish scrape results to queue: {str(e)}")
        raise
