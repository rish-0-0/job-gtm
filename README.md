# JOB BOARDS INTELLIGENCE PLATFORM GTM

## Architecture

This platform consists of:
- **PostgreSQL Database**: Persistent data storage (port 5432)
- **RabbitMQ**: Message queue for reliable job data processing (ports 5672, 15672)
- **Temporal Server**: Workflow orchestration engine (ports 7233, 8233)
- **Scraper Service**: API service for triggering web scrapers with Puppeteer pre-installed (port 6000)
- **Workflow Service**: FastAPI service for orchestrating scraping and AI workflows via Temporal (port 8000)
- **Queue Consumer**: Background service for processing scraped jobs from RabbitMQ
- **Ollama LLM**: GPU-accelerated local LLM service with Llama 3.2 3B (port 11434) - See [OLLAMA_SETUP.md](OLLAMA_SETUP.md)

## Prerequisites

- Docker and Docker Compose installed
- At least 5GB of free disk space
  - Puppeteer image: ~400MB
  - Ollama + Llama 3.2 3B model: ~2GB
  - Database and logs: ~2-3GB
- **For GPU support (Ollama)**: NVIDIA GPU with CUDA support + nvidia-container-toolkit
  - See [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for GPU setup instructions

## Building and Running

### Initial Setup

Build and start all services:

```bash
docker compose up -d --build
```

This will:
1. Start the PostgreSQL database on port 5432
2. Start the Temporal server on ports 7233, 8233
3. Build and start the scraper service on port 6000 with Puppeteer pre-installed (~200MB)
4. Build and start the workflow service on port 8000
5. **Automatically create and apply database migrations** (on first run)

### Rebuilding the Scraper Service

If you make changes to the scraper code, rebuild the image:

```bash
docker compose build scraper
docker compose up -d scraper
```

### Stopping Services

```bash
docker compose down
```

## API Endpoints

### Trigger All Scrapers

Start scraping workflow for all available scrapers:

```bash
curl -X POST http://localhost:8000/workflows/scrape/trigger
```

### Trigger Single Scraper

Start scraping workflow for a specific scraper:

```bash
# Dice scraper
curl -X POST http://localhost:8000/workflows/scrape/trigger/dice

# SimplyHired scraper
curl -X POST http://localhost:8000/workflows/scrape/trigger/simplyhired

# ZipRecruiter scraper
curl -X POST http://localhost:8000/workflows/scrape/trigger/ziprecruiter
```

### Delete PostgreSQL Data

To clear all scraped job data from the database:

```bash
docker compose exec postgres psql -U postgres -d jobgtm -c "TRUNCATE TABLE job_listings RESTART IDENTITY CASCADE;"
```