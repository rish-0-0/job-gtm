# RabbitMQ Queue Setup for Job Scraping

## Overview

The job scraping system now uses RabbitMQ as a message queue to decouple scraping from database writes. This improves reliability and ensures no data loss from write failures.

## Architecture

```
Scrapers → Temporal Workflow → RabbitMQ Queue → Consumer Workers → PostgreSQL
                                      ↓
                                Dead Letter Queue (failures)
```

### Components

1. **Scraper Service**: Scrapes job listings from various job boards
2. **Temporal Workflow**: Orchestrates scraping across multiple pages/sites
3. **RabbitMQ Producer**: Publishes scraped listings to the queue
4. **RabbitMQ Queue**: Buffers messages (durable, survives restarts)
5. **Consumer Workers**: Batch-process messages and write to database
6. **Dead Letter Queue (DLQ)**: Stores messages that failed after max retries

## Key Features

### 1. Durability
- Messages are persisted to disk (survive broker restarts)
- No data loss if consumer crashes or database is temporarily unavailable

### 2. Batch Processing
- Consumers process up to 50 messages per batch
- Significantly faster than individual inserts
- Configurable batch size and timeout

### 3. Dead Letter Queue
- Failed messages (after 3 retries) are sent to DLQ
- Manual inspection and recovery possible
- Prevents infinite retry loops

### 4. Backpressure Handling
- Queue naturally buffers when DB writes are slow
- Scrapers aren't blocked by database performance

### 5. Horizontal Scaling
- Run multiple consumer instances for parallel processing
- Just increase replicas in docker-compose

## Configuration

### Environment Variables

```bash
# RabbitMQ connection
RABBITMQ_URL=amqp://jobgtm:jobgtm_password@rabbitmq:5672/

# Database connection
DATABASE_URL=postgresql://jobgtm:jobgtm_password@postgres:5432/jobgtm
```

### Queue Configuration

Located in `workflow-svc/queue_config.py`:

```python
JOBS_QUEUE = "scraped_jobs"           # Main queue
JOBS_DLQ = "scraped_jobs_dlq"         # Dead letter queue
JOBS_EXCHANGE = "scraped_jobs_exchange"
DLX_EXCHANGE = "scraped_jobs_dlx"     # Dead letter exchange
```

### Consumer Configuration

Located in `workflow-svc/consumer.py`:

```python
BATCH_SIZE = 50          # Messages per batch
BATCH_TIMEOUT = 2.0      # Seconds to wait for batch
MAX_RETRIES = 3          # Retries before DLQ
```

## Running the System

### Start all services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- RabbitMQ (AMQP: 5672, Management UI: 15672)
- Temporal (ports 7233, 8233)
- Scraper service (port 6000)
- Workflow service (port 8000)
- Queue consumer (background)

### Access RabbitMQ Management UI

Open [http://localhost:15672](http://localhost:15672)

- Username: `jobgtm`
- Password: `jobgtm_password`

### Monitor Queue Status

In the RabbitMQ UI, you can:
- View message count in `scraped_jobs` queue
- Check consumer count
- Monitor message rates
- Inspect messages in DLQ
- View message acknowledgment rates

## Scaling

### Scale consumer workers

```bash
docker-compose up -d --scale queue-consumer=3
```

This runs 3 consumer instances in parallel for faster processing.

### Adjust batch size

Edit `workflow-svc/consumer.py`:

```python
BATCH_SIZE = 100  # Process 100 messages per batch
```

Larger batches = faster throughput, but more memory usage.

## Monitoring

### Check queue depth

```bash
docker exec rabbitmq-broker rabbitmqctl list_queues name messages messages_ready messages_unacknowledged
```

### Check consumer status

```bash
docker logs queue-consumer -f
```

### Check for messages in DLQ

```bash
docker exec rabbitmq-broker rabbitmqctl list_queues name messages | grep dlq
```

If you see messages in DLQ, inspect them in the RabbitMQ Management UI.

## Troubleshooting

### Messages stuck in queue

**Symptom**: Queue depth keeps growing, messages not being processed

**Solutions**:
1. Check consumer logs: `docker logs queue-consumer`
2. Verify database connection: Check `DATABASE_URL` environment variable
3. Scale up consumers: `docker-compose up -d --scale queue-consumer=5`

### Messages going to DLQ

**Symptom**: Messages appearing in `scraped_jobs_dlq`

**Solutions**:
1. Check consumer logs for error details
2. Inspect DLQ messages in RabbitMQ UI
3. Fix underlying issue (e.g., database constraint)
4. Manually requeue messages from DLQ if needed

### Consumer crashes

**Symptom**: Consumer container repeatedly restarting

**Solutions**:
1. Check logs: `docker logs queue-consumer`
2. Verify RabbitMQ is running: `docker ps | grep rabbitmq`
3. Check database connectivity
4. Ensure `aio-pika` is installed: `pip install -r requirements.txt`

### Database write failures

**Symptom**: High retry rate, messages timing out

**Solutions**:
1. Check database load and performance
2. Reduce batch size to lower memory usage
3. Add database indexes on frequently queried columns
4. Scale up PostgreSQL resources

## Data Flow Example

1. **Scraper extracts 100 jobs** from ZipRecruiter page 5
2. **Workflow publishes 100 messages** to `scraped_jobs` queue
3. **Consumer reads 50 messages** (batch 1)
4. **Consumer writes 50 jobs** to database in bulk
5. **40 succeed, 10 duplicates** (already in DB)
6. **All 50 messages acknowledged** (removed from queue)
7. **Consumer reads remaining 50 messages** (batch 2)
8. **48 succeed, 1 duplicate, 1 fails** (DB error)
9. **49 messages acknowledged, 1 requeued** for retry
10. **Failed message retried** (attempt 2 of 3)

## Benefits Over Direct Database Writes

### Before (Direct Writes)
- ❌ Write failures cause data loss
- ❌ Scrapers blocked by slow DB writes
- ❌ No visibility into failed writes
- ❌ Hard to scale database writes
- ❌ Duplicate handling slows down workflow

### After (Queue-Based)
- ✅ No data loss (messages persisted)
- ✅ Scrapers never blocked
- ✅ DLQ provides visibility into failures
- ✅ Easy to scale consumers horizontally
- ✅ Batch processing handles duplicates efficiently

## Performance

### Expected Throughput

- **Scraping**: ~1000 jobs/minute (depends on site)
- **Queue publishing**: ~10,000 messages/second
- **Consumer processing**: ~500-1000 jobs/second (single consumer)
- **Batch inserts**: 50 jobs/batch, ~2 seconds/batch

### With 5 Consumers

- **Total throughput**: ~2500-5000 jobs/second
- Can easily keep up with scraping rate

## Future Enhancements

- [ ] Add monitoring/alerting for queue depth
- [ ] Implement exponential backoff for retries
- [ ] Add message TTL (time-to-live) to prevent stale data
- [ ] Create separate queues per scraper source
- [ ] Add consumer metrics (Prometheus/Grafana)
- [ ] Implement priority queues for urgent jobs
