# Database Management

The workflow-svc controls the database schema using Alembic migrations.

## Architecture

- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Database**: PostgreSQL 16

## Database Models

### JobListing
Stores scraped job listings from various job boards.

**Fields:**
- `id`: Primary key
- `company_title`: Company name
- `job_role`: Job title
- `job_location`: Location
- `employment_type`: Full-time, contract, etc.
- `salary_range`: Original salary string
- `min_salary`, `max_salary`: Parsed salary values
- `required_experience`: Experience required
- `seniority_level`: Junior, senior, etc.
- `job_description`: Job description text
- `date_posted`: When the job was posted
- `posting_url`: Link to job posting (unique)
- `hiring_team`: Hiring team information
- `about_company`: Company description
- `scraper_source`: Which scraper was used (dice, simplyhired, etc.)
- `scraped_at`: When we scraped it
- `created_at`, `updated_at`: Timestamps

### WorkflowRun
Tracks Temporal workflow executions.

**Fields:**
- `id`: Primary key
- `workflow_id`: Temporal workflow ID (unique)
- `run_id`: Temporal run ID
- `workflow_type`: scrape, ai, etc.
- `status`: started, running, completed, failed
- `input_params`: JSON of input parameters
- `result`: JSON of workflow results
- `error_message`: Error details if failed
- `started_at`, `completed_at`: Timing information
- `created_at`, `updated_at`: Timestamps

## Migration Commands

### Create a New Migration

After modifying models, generate a migration:

```bash
# From workflow-svc directory
alembic revision --autogenerate -m "description of changes"
```

### Apply Migrations

Apply pending migrations to the database:

```bash
alembic upgrade head
```

### Rollback Migrations

Rollback the last migration:

```bash
alembic downgrade -1
```

Rollback to a specific revision:

```bash
alembic downgrade <revision_id>
```

### View Migration History

```bash
alembic history
```

### View Current Version

```bash
alembic current
```

## Docker Environment

Migrations run automatically when the workflow-svc container starts:

1. Container waits for PostgreSQL to be ready
2. Runs `python migrate.py` (which executes `alembic upgrade head`)
3. Starts the FastAPI application

## Local Development

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set DATABASE_URL environment variable:
```bash
export DATABASE_URL="postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm"
```

3. Run migrations:
```bash
python migrate.py
# or
alembic upgrade head
```

### Creating a New Model

1. Create model file in `models/` directory:
```python
from sqlalchemy import Column, Integer, String
from database import Base

class MyModel(Base):
    __tablename__ = "my_table"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
```

2. Import model in `models/__init__.py`:
```python
from .my_model import MyModel

__all__ = [..., "MyModel"]
```

3. Generate migration:
```bash
alembic revision --autogenerate -m "add my_model table"
```

4. Review the generated migration file in `alembic/versions/`

5. Apply the migration:
```bash
alembic upgrade head
```

## Manual Database Access

### From Docker Container

```bash
docker exec -it postgres-db psql -U jobgtm -d jobgtm
```

### From Host Machine

```bash
psql -h localhost -p 5432 -U jobgtm -d jobgtm
```

### Common SQL Queries

List all tables:
```sql
\dt
```

Describe a table:
```sql
\d job_listings
```

View migration history:
```sql
SELECT * FROM alembic_version;
```

Count job listings:
```sql
SELECT COUNT(*) FROM job_listings;
```

## Troubleshooting

### Migration conflicts

If you have migration conflicts:

```bash
# View current state
alembic current

# View history
alembic history

# Merge heads if needed
alembic merge heads -m "merge migrations"
```

### Reset database (DEVELOPMENT ONLY)

**WARNING: This will delete all data!**

```bash
# Stop containers
docker compose down

# Remove PostgreSQL data
rm -rf data/postgres

# Start containers (migrations will run automatically)
docker compose up -d
```

### Manual migration from SQL

If you need to run custom SQL:

```bash
alembic revision -m "custom sql changes"
```

Edit the generated file and add SQL:

```python
def upgrade():
    op.execute("""
        CREATE INDEX idx_job_listings_location
        ON job_listings(job_location);
    """)

def downgrade():
    op.execute("DROP INDEX idx_job_listings_location;")
```

## Best Practices

1. **Always review auto-generated migrations** before applying them
2. **Test migrations** on development data before production
3. **Write reversible migrations** - always implement both `upgrade()` and `downgrade()`
4. **Use transactions** - Alembic wraps migrations in transactions by default
5. **Commit migration files** to version control
6. **Don't modify applied migrations** - create new ones instead
7. **Use meaningful migration messages** that describe the changes
