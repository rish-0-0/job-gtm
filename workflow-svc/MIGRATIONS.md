# Database Migrations Guide

## Overview

**The workflow-svc service controls all database schema migrations.**

- **Tool**: Alembic (SQLAlchemy migration tool)
- **Location**: `workflow-svc/` directory
- **Models**: Defined in `workflow-svc/models/`
- **Migrations**: Auto-generated and stored in `workflow-svc/alembic/versions/`

## How It Works

1. **On Container Startup**:
   - The `entrypoint.sh` script waits for PostgreSQL to be ready
   - Runs `python migrate.py` which executes `alembic upgrade head`
   - Applies all pending migrations automatically
   - Then starts the FastAPI application

2. **During Development**:
   - Modify models in `models/` directory
   - Generate migration: `alembic revision --autogenerate -m "description"`
   - Review the generated migration file
   - Commit the migration file to version control
   - Next container restart will apply it automatically

## Initial Setup

When you first start the services, the initial migration will create:

- `job_listings` table - for storing scraped job data
- `workflow_runs` table - for tracking Temporal workflows
- `alembic_version` table - for tracking migration history

## Creating Your First Migration

After the initial setup, if you need to add a new table or modify the schema:

```bash
# 1. Enter the workflow-svc directory
cd workflow-svc

# 2. Modify a model file (e.g., models/job_listing.py)
# Add a new field:
#   new_field = Column(String(255))

# 3. Generate migration
alembic revision --autogenerate -m "add new_field to job_listings"

# 4. Review the generated file in alembic/versions/
# Make sure it looks correct!

# 5. Apply the migration locally (for testing)
alembic upgrade head

# 6. Test your changes

# 7. Commit the migration file
git add alembic/versions/*.py
git commit -m "Add new_field to job_listings"

# 8. Rebuild and restart the container
docker compose build workflow-svc
docker compose up -d workflow-svc
```

## Common Scenarios

### Adding a New Table

1. Create new model file in `models/`
2. Import it in `models/__init__.py`
3. Generate migration: `alembic revision --autogenerate -m "add my_table"`
4. Apply: `alembic upgrade head`

### Adding a Column

1. Add column to existing model
2. Generate migration: `alembic revision --autogenerate -m "add column to table"`
3. Apply: `alembic upgrade head`

### Removing a Column

1. Remove column from model
2. Generate migration: `alembic revision --autogenerate -m "remove column from table"`
3. Review migration - ensure data migration if needed
4. Apply: `alembic upgrade head`

### Custom SQL Migration

For complex changes that Alembic can't auto-generate:

```bash
alembic revision -m "custom changes"
```

Edit the generated file:
```python
def upgrade():
    op.execute("""
        -- Your custom SQL here
        UPDATE job_listings SET status = 'active' WHERE status IS NULL;
    """)

def downgrade():
    op.execute("""
        -- Reverse the changes
        UPDATE job_listings SET status = NULL WHERE status = 'active';
    """)
```

## Checking Migration Status

```bash
# View current migration version
alembic current

# View migration history
alembic history

# View pending migrations
alembic history --verbose
```

## Troubleshooting

### "Target database is not up to date"

This means there are pending migrations. Run:
```bash
alembic upgrade head
```

### "Can't locate revision identified by"

Migration file is missing or corrupt. Check `alembic/versions/` directory.

### "Multiple head revisions are present"

You have conflicting migration branches. Merge them:
```bash
alembic merge heads -m "merge migrations"
```

### Reset Everything (DEVELOPMENT ONLY)

**WARNING: Deletes all data!**

```bash
docker compose down
rm -rf data/postgres
docker compose up -d
```

## Best Practices

1. **Always review auto-generated migrations** - They're not always perfect
2. **Test migrations locally** before deploying
3. **Write reversible migrations** - Implement both upgrade and downgrade
4. **Use descriptive names** - "add_user_email_column" not "update_db"
5. **One logical change per migration** - Don't combine unrelated changes
6. **Never edit applied migrations** - Create a new migration instead
7. **Commit migration files** - They're part of your codebase
8. **Data migrations** - If removing/renaming columns with data, migrate the data first

## File Structure

```
workflow-svc/
├── alembic/                    # Alembic configuration
│   ├── versions/               # Migration files (auto-generated)
│   │   └── .gitkeep
│   ├── env.py                  # Alembic environment config
│   ├── script.py.mako          # Migration template
│   └── README
├── models/                     # SQLAlchemy models
│   ├── __init__.py
│   ├── job_listing.py
│   └── workflow_run.py
├── alembic.ini                 # Alembic config file
├── database.py                 # Database connection setup
├── migrate.py                  # Migration runner script
└── DATABASE.md                 # Detailed database docs
```

## Example Workflow

**Scenario**: Add an `is_active` boolean field to job listings

```bash
# 1. Edit the model
# In models/job_listing.py, add:
#   is_active = Column(Boolean, default=True, index=True)

# 2. Generate migration
cd workflow-svc
alembic revision --autogenerate -m "add is_active to job_listings"

# 3. Review the generated file
# Check alembic/versions/XXXX_add_is_active_to_job_listings.py

# 4. Test locally
alembic upgrade head

# 5. Verify in database
docker exec -it postgres-db psql -U jobgtm -d jobgtm -c "\d job_listings"

# 6. Commit
git add alembic/versions/*.py models/job_listing.py
git commit -m "Add is_active field to job listings"

# 7. Deploy (rebuild container)
docker compose build workflow-svc && docker compose up -d workflow-svc
```

## Reference

For more details, see:
- [workflow-svc/DATABASE.md](DATABASE.md) - Full database documentation
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
