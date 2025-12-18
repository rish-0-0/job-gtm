# Initial Setup Guide

## Automatic Setup (Recommended)

**The initial migration is created automatically!**

Just run:
```bash
docker compose up -d --build
```

The `init_setup.py` script will automatically:
1. Check if any migrations exist
2. If none exist, create an initial migration from the models
3. Apply the migration to the database
4. Start the application

**That's it!** No manual steps required.

## How It Works

When the container starts:
1. Wait for PostgreSQL to be ready
2. Run `init_setup.py` → Creates initial migration if needed
3. Run `migrate.py` → Applies all migrations
4. Start the FastAPI application

## Manual Setup (Advanced)

If you prefer to create the initial migration manually:

### Option 1: Create Initial Migration Before Starting Containers

```bash
# 1. Start only PostgreSQL
docker compose up -d postgres

# 2. Wait for PostgreSQL to be ready
docker compose logs -f postgres
# Wait until you see "database system is ready to accept connections"

# 3. Enter the workflow-svc directory
cd workflow-svc

# 4. Install dependencies locally (if not already done)
pip install -r requirements.txt

# 5. Create initial migration
export DATABASE_URL="postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm"
alembic revision --autogenerate -m "initial schema"

# 6. Review the generated migration file in alembic/versions/

# 7. Start all services
cd ..
docker compose up -d --build
```

### Option 2: Create Migration Inside Container

```bash
# 1. Start all services
docker compose up -d --build

# 2. The container will fail because no migrations exist - that's okay!

# 3. Enter the workflow-svc container
docker exec -it workflow-service bash

# 4. Create initial migration
alembic revision --autogenerate -m "initial schema"

# 5. Exit container
exit

# 6. Copy the migration file to your local machine
docker cp workflow-service:/app/alembic/versions/XXXX_initial_schema.py ./workflow-svc/alembic/versions/

# 7. Restart the container
docker compose restart workflow-svc
```

### Option 3: Manual Initial Migration (Recommended for First Setup)

Create the initial migration file manually:

```bash
cd workflow-svc

# Generate migration
alembic revision --autogenerate -m "initial schema"

# Or create it manually if you prefer
alembic revision -m "initial schema"
```

The migration will be created in `alembic/versions/XXXX_initial_schema.py`

Review and edit if needed, then commit it to git.

Next time you run `docker compose up`, the migration will apply automatically!

## Verifying Setup

After the containers start, check that migrations ran:

```bash
# 1. Check workflow-svc logs
docker compose logs workflow-svc

# You should see:
# "Running database migrations..."
# "✅ Migrations completed successfully"
# "Starting application..."

# 2. Check database tables
docker exec -it postgres-db psql -U jobgtm -d jobgtm -c "\dt"

# You should see:
#  public | alembic_version | table | jobgtm
#  public | job_listings    | table | jobgtm
#  public | workflow_runs   | table | jobgtm

# 3. Check migration version
docker exec -it postgres-db psql -U jobgtm -d jobgtm -c "SELECT * FROM alembic_version;"
```

## Quick Start (Recommended)

I'll create an initial migration file for you now:

```bash
cd workflow-svc

# Set DATABASE_URL to connect to localhost
export DATABASE_URL="postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm"

# Start only postgres first
docker compose up -d postgres

# Wait 5 seconds for it to be ready
sleep 5

# Create initial migration
alembic revision --autogenerate -m "initial schema"

# Now start all services
docker compose up -d --build
```

## Troubleshooting

### "No migration files found"

You need to create the initial migration. Follow Option 1 or Option 3 above.

### "Target database is not up to date"

This means migrations exist but haven't been applied. The entrypoint.sh should handle this automatically.

If you're running locally:
```bash
cd workflow-svc
alembic upgrade head
```

### Container keeps restarting

Check logs:
```bash
docker compose logs workflow-svc
```

Common issues:
- PostgreSQL not ready yet (wait a bit longer)
- Migration file syntax error (check the migration file)
- Database connection error (check DATABASE_URL)

### Reset Everything

If you need to start fresh:

```bash
# Stop everything
docker compose down

# Delete database data
rm -rf data/postgres

# Delete migration files (optional)
rm -rf workflow-svc/alembic/versions/*.py

# Start fresh
docker compose up -d --build
```

## Summary

The automatic migration flow is:

1. Container starts → `entrypoint.sh` runs
2. Wait for PostgreSQL to be ready
3. Run `python migrate.py`
4. Which runs `alembic upgrade head`
5. Alembic applies any pending migrations
6. App starts

**You only need to create migrations when you modify the database schema.**
**Migrations are applied automatically when the container starts.**
