# Job Boards Intelligence Platform

Scalable job scraping and AI enrichment pipeline.

## Architecture

```
Scrapers → RabbitMQ → AI Enrichment → PostgreSQL (pgvector)
              ↓
         Temporal (orchestration)
              ↓
         Redis (query cache)
```

**Stack:** PostgreSQL + pgvector, RabbitMQ, Temporal, Redis, Ollama (local LLM), Puppeteer

## FAQ

### How do you handle 50k requests without getting banned?

**List-page scraping, not detail-page scraping.** Each job board page returns ~20 jobs. To get 50k jobs, we make ~2,500 page requests instead of 50,000 individual job requests.

- Scrape listing pages only (job cards contain most metadata)
- Rate limiting with delays between requests
- User agent rotation
- Headless browser (Puppeteer) mimics real browser behavior

### How much would this cost in LLM tokens?

**Currently ~$0** - Dev uses local Ollama. Production costs depend on model choice.

**Token usage per operation:**

| Operation | Input Tokens | Output Tokens | Per 50k Jobs |
|-----------|-------------|---------------|--------------|
| AI Enrichment (per job) | ~1,800 | ~1,000 | 140M tokens |
| Text-to-SQL (per query) | ~1,200 | ~100 | N/A |
| Embeddings | N/A | N/A | Free (local) |

**Production cost estimates (50k jobs):**

| Model | AI Enrichment Cost |
|-------|-------------------|
| GPT-4o mini | ~$25 |
| Claude Haiku | ~$35 |
| GPT-4o | ~$500 |
| Claude Sonnet | ~$600 |

*AI enrichment uses smaller/cheaper models. Text-to-SQL uses better models but runs infrequently (user queries only).*

Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (384 dims, ~40ms CPU) - always free.

### How would you scale to 1 Million jobs?

1. **RabbitMQ queuing** - Decouples scraping from processing. Scraped jobs queue in `raw_jobs` → consumers process at their own pace → enriched jobs queue in `enriched_jobs` → final DB write. Handles backpressure naturally.

2. **Temporal workflows** - Orchestrates scraping across multiple job boards. Handles retries, failures, and distributed coordination.

3. **Batch processing** - Consumers process jobs in batches (configurable batch size/timeout). Reduces DB round-trips.

4. **Horizontal scaling** - Spin up more Temporal workers and queue consumers. Docker Compose already runs 2 worker replicas.

5. **pgvector** - Vector similarity search for semantic job matching. Scales with proper indexing (IVFFlat/HNSW).

6. **Redis caching** - Caches NL query results to reduce repeated LLM calls.

## Quick Start

```bash
docker compose up -d --build
```

Services: PostgreSQL (5432), RabbitMQ (5672/15672), Temporal (7233/8233), Redis (6379), Ollama (11434), API (8001), UI (3000)
