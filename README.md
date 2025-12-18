# JOB BOARDS INTELLIGENCE PLATFORM GTM

## Architecture

This platform consists of:
- **Temporal Server**: Workflow orchestration engine (ports 7233, 8233)
- **Scraper Service**: API service for triggering web scrapers with Puppeteer pre-installed (port 6000)

## Prerequisites

- Docker and Docker Compose installed
- At least 2GB of free disk space (Puppeteer image is ~400MB)

## Building and Running

### Initial Setup

Build and start all services:

```bash
docker compose up -d --build
```

This will:
1. Build the scraper Docker image with Puppeteer pre-installed (~200MB)
2. Start the Temporal server
3. Start the scraper service on port 6000

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

## Services

### Temporal UI

Access the Temporal web interface:

[http://localhost:8233](http://localhost:8233)

### Scraper API

The scraper service exposes the following endpoints:

**Base URL**: `http://localhost:6000`

#### List Available Scrapers

```bash
GET /scrapers
```

Example:
```bash
curl http://localhost:6000/scrapers
```

#### Trigger a Scraper

```bash
POST /scrape
Content-Type: application/json

{
  "scraper": "indeed",
  "params": {
    "location": "New York",
    "jobTitle": "Software Engineer"
  }
}
```

Example:
```bash
curl -X POST http://localhost:6000/scrape \
  -H "Content-Type: application/json" \
  -d '{"scraper": "indeed", "params": {"location": "New York"}}'
```

## Development

### Adding a New Scraper

1. Create a new scraper class in `scraper/src/scrapers/` that extends `JobBoardScraper`
2. Register it in `scraper/src/scrapers/index.ts`:

```typescript
import { NewScraper } from "./NewScraper";
scraperRegistry.register("newscraper", NewScraper);
```

3. Rebuild the Docker image:

```bash
docker compose build scraper
docker compose up -d scraper
```

### Logs

View scraper logs:

```bash
docker compose logs -f scraper
```

View all logs:

```bash
docker compose logs -f
```