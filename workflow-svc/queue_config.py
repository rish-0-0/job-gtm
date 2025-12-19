"""
RabbitMQ queue configuration and utilities
"""
import os
from typing import Optional
import aio_pika
from aio_pika import Connection, Channel, Queue, Exchange, ExchangeType
from aio_pika.abc import AbstractRobustConnection
import logging

logger = logging.getLogger(__name__)

# Queue names
JOBS_QUEUE = "scraped_jobs"
JOBS_DLQ = "scraped_jobs_dlq"

# Exchange names
JOBS_EXCHANGE = "scraped_jobs_exchange"
DLX_EXCHANGE = "scraped_jobs_dlx"

# RabbitMQ connection
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://jobgtm:jobgtm_password@localhost:5672/")

# Global connection and channel (for producer)
_connection: Optional[AbstractRobustConnection] = None
_channel: Optional[Channel] = None


async def get_rabbitmq_connection() -> AbstractRobustConnection:
    """
    Get or create a RabbitMQ connection
    """
    global _connection
    if _connection is None or _connection.is_closed:
        logger.info(f"Connecting to RabbitMQ at {RABBITMQ_URL}")
        _connection = await aio_pika.connect_robust(RABBITMQ_URL)
        logger.info("Connected to RabbitMQ")
    return _connection


async def get_rabbitmq_channel() -> Channel:
    """
    Get or create a RabbitMQ channel
    """
    global _channel
    if _channel is None or _channel.is_closed:
        connection = await get_rabbitmq_connection()
        _channel = await connection.channel()
        await _channel.set_qos(prefetch_count=10)  # Limit concurrent processing
        logger.info("Created RabbitMQ channel with QoS prefetch_count=10")
    return _channel


async def setup_queues() -> None:
    """
    Set up RabbitMQ queues, exchanges, and bindings with DLQ support
    """
    channel = await get_rabbitmq_channel()

    # Create Dead Letter Exchange (DLX)
    dlx = await channel.declare_exchange(
        DLX_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True
    )
    logger.info(f"Declared DLX exchange: {DLX_EXCHANGE}")

    # Create Dead Letter Queue (DLQ)
    dlq = await channel.declare_queue(
        JOBS_DLQ,
        durable=True
    )
    await dlq.bind(dlx, routing_key=JOBS_QUEUE)
    logger.info(f"Declared DLQ: {JOBS_DLQ}")

    # Create main exchange
    exchange = await channel.declare_exchange(
        JOBS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True
    )
    logger.info(f"Declared main exchange: {JOBS_EXCHANGE}")

    # Create main queue with DLX configuration
    main_queue = await channel.declare_queue(
        JOBS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": JOBS_QUEUE,
            # Optional: set message TTL if needed
            # "x-message-ttl": 86400000,  # 24 hours in milliseconds
        }
    )
    await main_queue.bind(exchange, routing_key=JOBS_QUEUE)
    logger.info(f"Declared main queue: {JOBS_QUEUE} with DLX routing")


async def close_rabbitmq_connection() -> None:
    """
    Close RabbitMQ connection gracefully
    """
    global _connection, _channel

    if _channel and not _channel.is_closed:
        await _channel.close()
        _channel = None
        logger.info("Closed RabbitMQ channel")

    if _connection and not _connection.is_closed:
        await _connection.close()
        _connection = None
        logger.info("Closed RabbitMQ connection")
