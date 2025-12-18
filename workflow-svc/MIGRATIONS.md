# Database Migrations Guide

## Overview

**The workflow-svc service controls all database schema migrations using a deterministic, version-controlled approach.**

- **Tool**: Alembic (SQLAlchemy migration tool)
- **Location**: `workflow-svc/` directory
- **Models**: Defined in `workflow-svc/models/`
- **Migrations**: Stored in `workflow-svc/alembic/versions/`
- **Strategy**: Deterministic migrations with version control

## Quick Start

### First Time Setup

```bash
docker compose up -d --build
```

That's it! The system will:
1. ✅ Wait for PostgreSQL to be ready
2. ✅ Initialize database if needed
3. ✅ Apply all migrations to database
4. ✅ Start the application

## How It Works

### Startup Flow

```
Container Starts
      ↓
entrypoint.py runs
      ↓
┌─────────────────────────┐
│ 1. Wait for PostgreSQL  │
│    pg_isready check     │
└─────────────────────────┘
      ↓
┌─────────────────────────┐
│ 2. Run init_db.py       │
│    - Check if tables    │
│      exist              │
│    - Check if alembic   │
│      initialized        │
│    - Stamp or migrate   │
└─────────────────────────┘
      ↓
┌─────────────────────────┐
│ 3. Start Temporal Worker│
└─────────────────────────┘
      ↓
┌─────────────────────────┐
│ 4. Start FastAPI App    │
└─────────────────────────┘
```

### init_db.py - Smart Initialization

This script intelligently handles three scenarios:

**Scenario 1: Fresh Database (no tables)**
- Runs `alembic upgrade head`
- Creates all tables from migrations
- Initializes alembic_version table

**Scenario 2: Existing Tables (no alembic_version)**
- Stamps database with current revision
- No schema changes applied (tables already exist)
- Useful when adopting migrations on existing database

**Scenario 3: Fully Initialized**
- Runs `alembic upgrade head`
- Applies only pending migrations
- Normal operation mode

## Migration Strategy

### Deterministic Migrations

All migrations are:
- ✅ **Manually created** - No auto-generation on startup
- ✅ **Version controlled** - Committed to git
- ✅ **Numbered sequentially** - Easy to track order
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Reversible** - Both upgrade and downgrade defined

### Current Migrations

**001_initial_schema.py** - Initial database schema
- Creates `job_listings` table
- Creates `workflow_runs` table
- Adds unique constraints:
  - `posting_url` - prevents duplicate URLs
  - `uq_job_listing_details` - prevents duplicate jobs (company, role, location, type)
- Creates all indexes

## Creating New Migrations

### Step 1: Modify Your Models

```python
# In models/job_listing.py
class JobListing(Base):
    # ... existing fields ...
    new_field = Column(String(255))  # Add new field
```

### Step 2: Generate Migration

```bash
cd workflow-svc

# Generate migration file
alembic revision --autogenerate -m "add new_field to job_listings"
```

This creates a file like: `002_add_new_field_to_job_listings.py`

### Step 3: Review the Migration

**IMPORTANT**: Always review auto-generated migrations!

```bash
# View the generated file
cat alembic/versions/002_add_new_field_to_job_listings.py
```

Check for:
- Correct column types
- Proper nullable settings
- Expected indexes
- Data migration needs

### Step 4: Test Locally

```bash
# Apply migration
alembic upgrade head

# Verify in database
docker exec postgres-db psql -U jobgtm -d jobgtm -c "\d job_listings"
```

### Step 5: Commit to Git

```bash
git add alembic/versions/002_add_new_field_to_job_listings.py
git add models/job_listing.py
git commit -m "Add new_field to job_listings"
```

### Step 6: Deploy

```bash
docker compose build workflow-svc
docker compose up -d workflow-svc
```

The migration applies automatically on startup!

## Common Scenarios

### Adding a New Table

1. Create model file in `models/`
2. Import it in `models/__init__.py`
3. Generate migration: `alembic revision --autogenerate -m "add my_table"`
4. Review and test
5. Commit and deploy

### Adding a Column

```python
# models/job_listing.py
is_active = Column(Boolean, default=True, index=True)
```

```bash
alembic revision --autogenerate -m "add is_active to job_listings"
# Review, test, commit, deploy
```

### Adding a Unique Constraint

```python
# models/job_listing.py
class JobListing(Base):
    __tablename__ = "job_listings"
    __table_args__ = (
        UniqueConstraint('company_title', 'job_role', name='uq_company_role'),
    )
```

```bash
alembic revision --autogenerate -m "add unique constraint company_role"
# Review, test, commit, deploy
```

### Removing a Column

```python
# Remove from model
# is_active = Column(Boolean)  # REMOVED
```

```bash
alembic revision --autogenerate -m "remove is_active from job_listings"
```

**Important**: If column has data you need to preserve:

```python
# In the migration file
def upgrade():
    # 1. Create new column
    op.add_column('job_listings', sa.Column('status', sa.String(50)))

    # 2. Migrate data
    op.execute("UPDATE job_listings SET status = 'active' WHERE is_active = true")
    op.execute("UPDATE job_listings SET status = 'inactive' WHERE is_active = false")

    # 3. Remove old column
    op.drop_column('job_listings', 'is_active')
```

### Custom SQL Migration

For complex changes Alembic can't auto-generate:

```bash
alembic revision -m "migrate job status values"
```

Edit the file:
```python
def upgrade():
    op.execute("""
        UPDATE job_listings
        SET status = 'archived'
        WHERE created_at < NOW() - INTERVAL '90 days'
    """)

def downgrade():
    op.execute("""
        UPDATE job_listings
        SET status = 'active'
        WHERE status = 'archived'
    """)
```

## Checking Migration Status

```bash
# View current version
alembic current

# View migration history
alembic history

# View pending migrations
alembic history --verbose
```

## Viewing Logs

```bash
docker compose logs -f workflow-svc
```

### Successful Startup Logs

```
workflow-svc | Waiting for postgres...
workflow-svc | PostgreSQL is ready!
workflow-svc | Initializing database...
workflow-svc | ✅ Database already initialized
workflow-svc | 📋 Database initialized, checking for pending migrations...
workflow-svc | 🔄 Running database migrations...
workflow-svc | INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, add new field
workflow-svc | ✅ Migrations completed successfully
workflow-svc | Starting Temporal worker...
workflow-svc | ✅ Temporal worker started
workflow-svc | Starting FastAPI application...
workflow-svc | INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Troubleshooting

### "Can't locate revision identified by"

**Problem**: Migration file missing or alembic_version table out of sync

**Solution 1**: Check migration files exist
```bash
ls workflow-svc/alembic/versions/
```

**Solution 2**: Reset alembic version
```bash
docker exec postgres-db psql -U jobgtm -d jobgtm -c "DROP TABLE alembic_version;"
docker compose restart workflow-svc
```

### "Target database is not up to date"

**Problem**: Pending migrations not applied

**Solution**:
```bash
docker exec workflow-service alembic upgrade head
```

### "Multiple head revisions are present"

**Problem**: Conflicting migration branches

**Solution**: Merge migrations
```bash
alembic merge heads -m "merge migrations"
```

### Container Keeps Restarting

**Check logs**:
```bash
docker compose logs workflow-svc
```

**Common causes**:
- PostgreSQL not ready (wait 30 seconds)
- Migration syntax error (review migration file)
- Database connection error (check DATABASE_URL)
- Model import error (check models/__init__.py)

### "No module named 'database'"

**Problem**: Migration can't import models

**Check**:
- All model files are in `models/` directory
- Models imported in `models/__init__.py`
- `database.py` exists in workflow-svc root

### Reset Everything (DEVELOPMENT ONLY)

**WARNING: Deletes all data!**

```bash
docker compose down
rm -rf data/postgres
docker compose up -d --build
```

## Best Practices

1. ✅ **Always review auto-generated migrations** - They're not always perfect
2. ✅ **Test migrations locally** before deploying
3. ✅ **Write reversible migrations** - Implement both upgrade and downgrade
4. ✅ **Use descriptive names** - "add_user_email_column" not "update_db"
5. ✅ **One logical change per migration** - Don't combine unrelated changes
6. ✅ **Never edit applied migrations** - Create a new migration instead
7. ✅ **Commit migration files** - They're part of your codebase
8. ✅ **Handle data migrations carefully** - Migrate data before removing columns
9. ✅ **Number migrations sequentially** - Use 001, 002, 003, etc.
10. ✅ **Keep migrations deterministic** - No auto-generation on startup

## File Structure

```
workflow-svc/
├── alembic/                    # Alembic configuration
│   ├── versions/               # Migration files (version controlled)
│   │   ├── __init__.py
│   │   └── 001_initial_schema.py
│   ├── env.py                  # Alembic environment config
│   ├── script.py.mako          # Migration template
│   └── README
├── models/                     # SQLAlchemy models
│   ├── __init__.py
│   ├── job_listing.py
│   └── workflow_run.py
├── alembic.ini                 # Alembic config file
├── database.py                 # Database connection setup
├── init_db.py                  # Smart initialization script
├── migrate.py                  # Migration runner (legacy)
├── entrypoint.py               # Container entrypoint
└── MIGRATIONS.md               # This file
```

## Example Workflow

**Scenario**: Add an `is_remote` boolean field to job listings

```bash
# 1. Edit the model
# In models/job_listing.py, add:
#   is_remote = Column(Boolean, default=False, index=True)

# 2. Generate migration
cd workflow-svc
alembic revision --autogenerate -m "add is_remote to job_listings"

# 3. Review the generated file
cat alembic/versions/002_add_is_remote_to_job_listings.py

# Output should show:
# def upgrade():
#     op.add_column('job_listings', sa.Column('is_remote', sa.Boolean(), nullable=True))
#     op.create_index(op.f('ix_job_listings_is_remote'), 'job_listings', ['is_remote'])

# 4. Test locally
alembic upgrade head

# 5. Verify in database
docker exec postgres-db psql -U jobgtm -d jobgtm -c "\d job_listings"

# 6. Commit
git add alembic/versions/002_add_is_remote_to_job_listings.py
git add models/job_listing.py
git commit -m "Add is_remote field to job listings"

# 7. Deploy (rebuild container)
docker compose build workflow-svc && docker compose up -d workflow-svc

# 8. Verify logs
docker compose logs -f workflow-svc
# Should see: "Running upgrade 001 -> 002, add is_remote to job_listings"
```

## Database Schema

### Current Tables

**job_listings** - Stores scraped job postings
- Primary key: `id`
- Unique constraints:
  - `posting_url` (individual)
  - `(company_title, job_role, job_location, employment_type)` (composite)
- Indexes: company_title, job_role, job_location, scraper_source, posting_url

**workflow_runs** - Tracks Temporal workflow executions
- Primary key: `id`
- Unique constraint: `workflow_id`

**alembic_version** - Tracks applied migrations
- Single row with current revision number

## Summary

**Migration Philosophy**: Deterministic, version-controlled, and safe.

- ✅ All migrations committed to git
- ✅ Automatic application on startup
- ✅ Smart initialization handles any database state
- ✅ Easy rollback with downgrade functions
- ✅ No surprises - explicit, reviewable changes

For more details, see:
- [Database Schema Documentation](DATABASE.md)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
