# Workflow Service

FastAPI service for orchestrating scraping and AI workflows using Temporal.

## Quick Start

```bash
# From project root
docker compose up -d --build
```

✅ **Database migrations are created and applied automatically on first run!**

See [AUTO_MIGRATIONS.md](AUTO_MIGRATIONS.md) for details.

## Structure

```
workflow-svc/
├── app.py                  # FastAPI application with workflow endpoints
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker build configuration
├── workflows/             # Temporal workflow definitions
│   ├── scrape_workflow.py # Scraping workflow
│   └── ai_workflow.py     # AI processing workflow
└── activities/            # Temporal activities (tasks)
    ├── scrape_activities.py # Scraping-related activities
    └── ai_activities.py     # AI-related activities
```

## Workflows

### Scrape Workflow
Orchestrates the process of scraping job boards:
1. Calls the scraper service
2. Stores raw results
3. Returns job listings

### AI Workflow
Orchestrates AI model processing:
1. Preprocesses job listings
2. Runs AI model inference
3. Post-processes results
4. Stores results

## API Endpoints

### Health Check
```bash
GET /health
```

### Start Scraping Workflow
```bash
POST /workflows/scrape
{
  "scraper": "dice",
  "page": 1,
  "params": {}
}
```

### Start AI Workflow
```bash
POST /workflows/ai
{
  "job_listings": [],
  "model_type": "classification",
  "params": {}
}
```

### Get Workflow Status
```bash
GET /workflows/{workflow_id}
```

## Development

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the service:
```bash
python app.py
```

3. Access the API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Adding New Workflows

1. Create a new workflow in `workflows/`:
```python
from temporalio import workflow

@workflow.defn
class MyNewWorkflow:
    @workflow.run
    async def run(self, params):
        # Workflow logic here
        pass
```

2. Create corresponding activities in `activities/`:
```python
from temporalio import activity

@activity.defn
async def my_activity(param):
    # Activity logic here
    pass
```

3. Add a new endpoint in `app.py`:
```python
@app.post("/workflows/mynew")
async def start_new_workflow(request: MyRequest):
    # Start workflow logic
    pass
```

## Environment Variables

- `TEMPORAL_ADDRESS`: Temporal server address (default: `localhost:7233`)
- `PORT`: Service port (default: `8000`)
- `SCRAPER_URL`: Scraper service URL (default: `http://scraper:6000`)
