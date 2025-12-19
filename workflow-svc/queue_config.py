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

# Enrichment pipeline queue names
RAW_JOBS_QUEUE = "raw_jobs_for_processing"
RAW_JOBS_DLQ = "raw_jobs_for_processing_dlq"
ENRICHED_JOBS_QUEUE = "enriched_jobs"
ENRICHED_JOBS_DLQ = "enriched_jobs_dlq"

# Exchange names
JOBS_EXCHANGE = "scraped_jobs_exchange"
DLX_EXCHANGE = "scraped_jobs_dlx"

# Enrichment pipeline exchange names
RAW_JOBS_EXCHANGE = "raw_jobs_exchange"
RAW_JOBS_DLX = "raw_jobs_dlx"
ENRICHED_JOBS_EXCHANGE = "enriched_jobs_exchange"
ENRICHED_JOBS_DLX = "enriched_jobs_dlx"

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

    # ========== Original scraped_jobs queue setup ==========

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
        }
    )
    await main_queue.bind(exchange, routing_key=JOBS_QUEUE)
    logger.info(f"Declared main queue: {JOBS_QUEUE} with DLX routing")

    # ========== Enrichment pipeline: raw_jobs_for_processing queue ==========

    # Create DLX for raw jobs
    raw_jobs_dlx = await channel.declare_exchange(
        RAW_JOBS_DLX,
        ExchangeType.DIRECT,
        durable=True
    )
    logger.info(f"Declared DLX exchange: {RAW_JOBS_DLX}")

    # Create DLQ for raw jobs
    raw_jobs_dlq = await channel.declare_queue(
        RAW_JOBS_DLQ,
        durable=True
    )
    await raw_jobs_dlq.bind(raw_jobs_dlx, routing_key=RAW_JOBS_QUEUE)
    logger.info(f"Declared DLQ: {RAW_JOBS_DLQ}")

    # Create main exchange for raw jobs
    raw_jobs_exchange = await channel.declare_exchange(
        RAW_JOBS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True
    )
    logger.info(f"Declared exchange: {RAW_JOBS_EXCHANGE}")

    # Create raw jobs queue with DLX configuration
    raw_jobs_queue = await channel.declare_queue(
        RAW_JOBS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": RAW_JOBS_DLX,
            "x-dead-letter-routing-key": RAW_JOBS_QUEUE,
        }
    )
    await raw_jobs_queue.bind(raw_jobs_exchange, routing_key=RAW_JOBS_QUEUE)
    logger.info(f"Declared queue: {RAW_JOBS_QUEUE} with DLX routing")

    # ========== Enrichment pipeline: enriched_jobs queue ==========

    # Create DLX for enriched jobs
    enriched_jobs_dlx = await channel.declare_exchange(
        ENRICHED_JOBS_DLX,
        ExchangeType.DIRECT,
        durable=True
    )
    logger.info(f"Declared DLX exchange: {ENRICHED_JOBS_DLX}")

    # Create DLQ for enriched jobs
    enriched_jobs_dlq = await channel.declare_queue(
        ENRICHED_JOBS_DLQ,
        durable=True
    )
    await enriched_jobs_dlq.bind(enriched_jobs_dlx, routing_key=ENRICHED_JOBS_QUEUE)
    logger.info(f"Declared DLQ: {ENRICHED_JOBS_DLQ}")

    # Create main exchange for enriched jobs
    enriched_jobs_exchange = await channel.declare_exchange(
        ENRICHED_JOBS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True
    )
    logger.info(f"Declared exchange: {ENRICHED_JOBS_EXCHANGE}")

    # Create enriched jobs queue with DLX configuration
    enriched_jobs_queue = await channel.declare_queue(
        ENRICHED_JOBS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": ENRICHED_JOBS_DLX,
            "x-dead-letter-routing-key": ENRICHED_JOBS_QUEUE,
        }
    )
    await enriched_jobs_queue.bind(enriched_jobs_exchange, routing_key=ENRICHED_JOBS_QUEUE)
    logger.info(f"Declared queue: {ENRICHED_JOBS_QUEUE} with DLX routing")


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
