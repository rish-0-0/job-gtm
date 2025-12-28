"""
RabbitMQ queue configuration for the helper consumer.
Simplified version - only needs queue/exchange names.
Queues are already set up on the main system.
"""
import os

# Queue names (must match main system)
RAW_JOBS_QUEUE = "raw_jobs_for_processing"
RAW_JOBS_DLQ = "raw_jobs_for_processing_dlq"
ENRICHED_JOBS_QUEUE = "enriched_jobs"
ENRICHED_JOBS_DLQ = "enriched_jobs_dlq"

# Exchange names (must match main system)
RAW_JOBS_EXCHANGE = "raw_jobs_exchange"
RAW_JOBS_DLX = "raw_jobs_dlx"
ENRICHED_JOBS_EXCHANGE = "enriched_jobs_exchange"
ENRICHED_JOBS_DLX = "enriched_jobs_dlx"

# RabbitMQ connection URL (configured via environment variable)
# This should point to the main laptop's RabbitMQ instance
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://jobgtm:jobgtm_password@localhost:5672/")
