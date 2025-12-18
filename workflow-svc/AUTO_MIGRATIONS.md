# Automatic Migration System

## Overview

Database migrations are **completely automated**. You don't need to run any manual commands!

## First Time Setup

```bash
docker compose up -d --build
```

That's it! The system will:
1. ✅ Wait for PostgreSQL to be ready
2. ✅ Check if migrations exist
3. ✅ If none exist, create initial migration from models
4. ✅ Apply all migrations to database
5. ✅ Start the application

## How It Works

### Startup Flow

```
Container Starts
      ↓
entrypoint.sh runs
      ↓
┌─────────────────────────┐
│ 1. Wait for PostgreSQL  │
│    pg_isready check     │
└─────────────────────────┘
      ↓
┌─────────────────────────┐
│ 2. Run init_setup.py    │ ← NEW! Auto-creates initial migration
│    - Check if migrations│
│      exist              │
│    - If not, create one │
└─────────────────────────┘
      ↓
┌─────────────────────────┐
│ 3. Run migrate.py       │
│    alembic upgrade head │
└─────────────────────────┘
      ↓
┌─────────────────────────┐
│ 4. Start FastAPI App    │
└─────────────────────────┘
```

### init_setup.py

This script runs on every container start and:

1. **Checks** if `alembic/versions/` contains any migration files
2. **If yes**: Does nothing, skips to migration step
3. **If no**: Runs `alembic revision --autogenerate -m "initial schema"`
4. **Creates**: A migration file based on your SQLAlchemy models

### migrate.py

This script:

1. Runs `alembic upgrade head`
2. Applies all pending migrations
3. Updates the `alembic_version` table

## When You Modify Models

```python
# Edit models/job_listing.py
class JobListing(Base):
    # ... existing fields ...
    new_field = Column(String(255))  # Added new field
```

Then:

```bash
# 1. Create migration
cd workflow-svc
alembic revision --autogenerate -m "add new_field to job_listings"

# 2. Review the generated file
cat alembic/versions/XXXX_add_new_field_to_job_listings.py

# 3. Commit it
git add alembic/versions/*.py
git commit -m "Add new_field to job_listings"

# 4. Rebuild container
docker compose build workflow-svc
docker compose up -d workflow-svc
```

The migration will apply automatically on startup!

## Viewing Logs

To see the automatic migration process:

```bash
docker compose logs -f workflow-svc
```

You'll see output like:

```
workflow-svc | Waiting for postgres...
workflow-svc | PostgreSQL is ready!
workflow-svc | Checking initial setup...
workflow-svc | 🔍 Checking for existing migrations...
workflow-svc | ✅ Migrations already exist. Skipping initial setup.
workflow-svc | Running database migrations...
workflow-svc | INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial schema
workflow-svc | ✅ Migrations completed successfully
workflow-svc | Starting application...
```

## Common Scenarios

### First Time Running

```
🔍 Checking for existing migrations...
⚠️  No migrations found. Running initial setup...
📝 No migrations found. Creating initial schema migration...
✅ Initial migration created successfully
✅ Initial setup completed successfully
Running database migrations...
✅ Migrations completed successfully
Starting application...
```

### Subsequent Runs (No Changes)

```
🔍 Checking for existing migrations...
✅ Migrations already exist. Skipping initial setup.
Running database migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
✅ Migrations completed successfully
Starting application...
```

### Subsequent Runs (New Migration)

```
🔍 Checking for existing migrations...
✅ Migrations already exist. Skipping initial setup.
Running database migrations...
INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add new field
✅ Migrations completed successfully
Starting application...
```

## What Gets Created

On first run, the database will have:

### Tables

- `job_listings` - Scraped job data
- `workflow_runs` - Temporal workflow tracking
- `alembic_version` - Migration version tracking

### Migration File

Example: `alembic/versions/2024_01_15_1430-abc123_initial_schema.py`

```python
def upgrade() -> None:
    op.create_table('job_listings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_title', sa.String(length=255), nullable=False),
        # ... all other columns ...
        sa.PrimaryKeyConstraint('id')
    )
    # ... indexes and other tables ...

def downgrade() -> None:
    op.drop_table('workflow_runs')
    op.drop_table('job_listings')
```

## Troubleshooting

### Container Keeps Restarting

Check logs:
```bash
docker compose logs workflow-svc
```

Common issues:
- PostgreSQL not ready yet (wait 30 seconds)
- Migration syntax error (check migration file)
- Database connection error (check DATABASE_URL)

### "No module named 'database'"

The migration is trying to import models but can't find them. Make sure:
- All model files are in `models/` directory
- Models are imported in `models/__init__.py`
- `database.py` is in the root of `workflow-svc/`

### Want to Reset Everything

```bash
docker compose down
rm -rf data/postgres
rm -rf workflow-svc/alembic/versions/*.py  # Removes migrations
docker compose up -d --build
```

This will create everything from scratch.

## Manual Override

If you want to disable automatic migration creation:

```bash
# Option 1: Create a dummy migration file
touch workflow-svc/alembic/versions/dummy.py

# Option 2: Modify init_setup.py to always skip
# (not recommended)
```

## Best Practices

1. ✅ **Let init_setup.py handle first-time setup**
2. ✅ **Review auto-generated migrations** before committing
3. ✅ **Commit migration files** to version control
4. ✅ **Never edit applied migrations** - create new ones
5. ✅ **Test migrations locally** before deploying

## Summary

**You don't need to do anything!**

- First run: Migration created automatically
- Every run: Migrations applied automatically
- New changes: Just create migration and rebuild container

The system handles everything else! 🎉
