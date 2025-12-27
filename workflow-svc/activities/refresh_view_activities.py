"""
Temporal activities for refreshing materialized views.
"""
import json
import time
import logging
from typing import Dict, Any
from temporalio import activity
from sqlalchemy import text
import aio_pika

from database import SessionLocal
from queue_config import get_rabbitmq_channel

logger = logging.getLogger(__name__)

# Notifications exchange and queue
NOTIFICATIONS_EXCHANGE = "notifications_exchange"
NOTIFICATIONS_QUEUE = "notifications"


def get_allowed_views(db) -> list:
    """
    Get list of allowed materialized views, including custom views from database.
    """
    # Static system views
    system_views = [
        "mv_root_data",
        "mv_jobs_by_seniority",
        "mv_jobs_by_location",
        "mv_jobs_by_company",
        "mv_jobs_by_role",
        "mv_jobs_by_source",
        "mv_salary_distribution",
    ]

    # Fetch custom views from database
    try:
        result = db.execute(
            text("SELECT view_name FROM custom_materialized_views WHERE status = 'completed'")
        )
        custom_views = [row[0] for row in result.fetchall()]
        return system_views + custom_views
    except Exception:
        # Table might not exist yet
        return system_views


@activity.defn
async def refresh_materialized_view(view_name: str) -> Dict[str, Any]:
    """
    Refresh a materialized view in PostgreSQL.

    Args:
        view_name: Name of the materialized view to refresh

    Returns:
        Dictionary with refresh results
    """
    logger.info(f"[Refresh Activity] Starting refresh for view: {view_name}")

    db = SessionLocal()
    start_time = time.time()

    try:
        # Validate view name to prevent SQL injection
        allowed_views = get_allowed_views(db)

        if view_name not in allowed_views:
            raise ValueError(f"Invalid view name: {view_name}. Allowed views: {allowed_views}")

        # Check if view exists
        check_query = text("""
            SELECT COUNT(*)
            FROM pg_matviews
            WHERE matviewname = :view_name
        """)
        result = db.execute(check_query, {"view_name": view_name})
        count = result.scalar()

        if count == 0:
            raise ValueError(f"Materialized view {view_name} does not exist")

        # Refresh the materialized view
        # Using CONCURRENTLY allows reads during refresh (requires unique index)
        logger.info(f"[Refresh Activity] Executing REFRESH MATERIALIZED VIEW {view_name}")

        try:
            # Try concurrent refresh first (non-blocking)
            refresh_query = text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
            db.execute(refresh_query)
        except Exception as e:
            # Fall back to regular refresh if concurrent fails (e.g., no unique index)
            if "cannot refresh" in str(e).lower() or "unique index" in str(e).lower():
                logger.warning(f"[Refresh Activity] Concurrent refresh failed, using regular refresh: {e}")
                refresh_query = text(f"REFRESH MATERIALIZED VIEW {view_name}")
                db.execute(refresh_query)
            else:
                raise

        db.commit()

        # Get row count after refresh
        count_query = text(f"SELECT COUNT(*) FROM {view_name}")
        result = db.execute(count_query)
        rows = result.scalar()

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"[Refresh Activity] ✅ Refreshed {view_name}: {rows} rows in {duration_ms}ms"
        )

        return {
            "view_name": view_name,
            "rows": rows,
            "duration_ms": duration_ms,
            "status": "completed"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Refresh Activity] ❌ Failed to refresh {view_name}: {str(e)}")
        raise
    finally:
        db.close()


@activity.defn
async def publish_view_refresh_notification(
    view_name: str,
    status: str,
    details: Dict[str, Any]
) -> bool:
    """
    Publish a notification that a view refresh has completed.

    Args:
        view_name: Name of the view that was refreshed
        status: Status of the refresh (completed, failed)
        details: Additional details about the refresh

    Returns:
        True if notification was published successfully
    """
    logger.info(f"[Notification Activity] Publishing notification for {view_name}: {status}")

    try:
        channel = await get_rabbitmq_channel()

        # Declare notifications exchange (topic type for flexibility)
        exchange = await channel.declare_exchange(
            NOTIFICATIONS_EXCHANGE,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        # Declare notifications queue
        queue = await channel.declare_queue(
            NOTIFICATIONS_QUEUE,
            durable=True
        )
        await queue.bind(exchange, routing_key="view.refresh.*")

        # Create notification message
        notification = {
            "type": "view_refresh",
            "view_name": view_name,
            "status": status,
            "details": details,
            "timestamp": time.time()
        }

        # Publish notification
        message = aio_pika.Message(
            body=json.dumps(notification).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        routing_key = f"view.refresh.{status}"
        await exchange.publish(message, routing_key=routing_key)

        logger.info(f"[Notification Activity] ✅ Published notification: {routing_key}")
        return True

    except Exception as e:
        logger.error(f"[Notification Activity] ❌ Failed to publish notification: {str(e)}")
        raise
