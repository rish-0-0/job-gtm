# JOB BOARDS INTELLIGENCE PLATFORM GTM

## Architecture

This platform consists of:
- **PostgreSQL Database**: Persistent data storage (port 5432)
- **Temporal Server**: Workflow orchestration engine (ports 7233, 8233)
- **Scraper Service**: API service for triggering web scrapers with Puppeteer pre-installed (port 6000)
- **Workflow Service**: FastAPI service for orchestrating scraping and AI workflows via Temporal (port 8000)

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

## Services

### PostgreSQL Database

The PostgreSQL database is accessible to all services in the Docker network.

**Connection Details:**
- Host: `postgres` (within Docker network) or `localhost` (from host machine)
- Port: `5432`
- Database: `jobgtm`
- Username: `jobgtm`
- Password: `jobgtm_password`
- Connection URL: `postgresql://jobgtm:jobgtm_password@postgres:5432/jobgtm`

**Connect from host machine:**
```bash
psql -h localhost -p 5432 -U jobgtm -d jobgtm
```

**Connect from Docker services:**
All services have the `DATABASE_URL` environment variable configured.

### Temporal UI

Access the Temporal web interface:

[http://localhost:8233](http://localhost:8233)

### Workflow Service API

The workflow service orchestrates scraping and AI workflows using Temporal.

**Base URL**: `http://localhost:8000`

#### Health Check

```bash
GET /health
```

Example:
```bash
curl http://localhost:8000/health
```

#### Start Scraping Workflow

```bash
POST /workflows/scrape
Content-Type: application/json

{
  "scraper": "dice",
  "page": 1,
  "params": {}
}
```

Example:
```bash
curl -X POST http://localhost:8000/workflows/scrape \
  -H "Content-Type: application/json" \
  -d '{"scraper": "dice", "page": 1}'
```

#### Start AI Processing Workflow

```bash
POST /workflows/ai
Content-Type: application/json

{
  "job_listings": [],
  "model_type": "classification",
  "params": {}
}
```

Example:
```bash
curl -X POST http://localhost:8000/workflows/ai \
  -H "Content-Type: application/json" \
  -d '{"job_listings": [], "model_type": "classification"}'
```

#### Get Workflow Status

```bash
GET /workflows/{workflow_id}
```

Example:
```bash
curl http://localhost:8000/workflows/scrape-dice-123
```

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

#### Trigger a Scraper (Direct)

```bash
POST /scrape
Content-Type: application/json

{
  "scraper": "dice",
  "params": {}
}
```

Example:
```bash
curl -X POST http://localhost:6000/scrape \
  -H "Content-Type: application/json" \
  -d '{"scraper": "dice", "params": {}}'
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

### Adding a New Workflow

1. Create a new workflow class in `workflow-svc/workflows/` that extends Temporal's workflow
2. Create corresponding activities in `workflow-svc/activities/`
3. Add a new route in `workflow-svc/app.py` to trigger the workflow

### Database Management

**Schema & Migrations:**

Database schema is managed by the workflow-svc using Alembic migrations.

See [workflow-svc/DATABASE.md](workflow-svc/DATABASE.md) for detailed migration documentation.

**Quick Commands:**

Access PostgreSQL container:
```bash
docker exec -it postgres-db psql -U jobgtm -d jobgtm
```

Create a new migration (after modifying models):
```bash
cd workflow-svc
alembic revision --autogenerate -m "description"
```

Apply migrations (automatic on container startup):
```bash
cd workflow-svc
alembic upgrade head
```

View database logs:
```bash
docker compose logs -f postgres
```

### Logs

View workflow service logs:

```bash
docker compose logs -f workflow-svc
```

View scraper logs:

```bash
docker compose logs -f scraper
```

View all logs:

```bash
docker compose logs -f
```

### Data Persistence

PostgreSQL data is persisted in the local `./data/postgres` directory. This ensures:
- Data survives container restarts and rebuilds
- Easy access to database files from the host machine
- Data is preserved across `docker compose down` commands

The `data/` directory is git-ignored but remains on your local filesystem.

**To completely remove all database data:**

```bash
# Stop containers
docker compose down

# Remove data directory
rm -rf data/postgres
# On Windows: rmdir /s /q data\postgres
```

**Warning:** This will delete all database data permanently.