#!/usr/bin/env python
"""
Database initialization script
Only runs migrations if database needs setup
"""
import subprocess
import sys
from sqlalchemy import create_engine, text, inspect
import os

def check_database_initialized():
    """Check if database has been initialized"""
    try:
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://jobgtm:jobgtm_password@postgres:5432/jobgtm')
        engine = create_engine(DATABASE_URL)

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # Check if our main tables exist
        has_tables = 'job_listings' in tables and 'workflow_runs' in tables

        if has_tables:
            print("✅ Database already initialized")
            return True
        else:
            print("📋 Database needs initialization")
            return False

    except Exception as e:
        print(f"⚠️  Could not check database state: {str(e)}")
        return False

def check_alembic_initialized():
    """Check if alembic version table exists"""
    try:
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://jobgtm:jobgtm_password@postgres:5432/jobgtm')
        engine = create_engine(DATABASE_URL)

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        return 'alembic_version' in tables

    except Exception as e:
        print(f"⚠️  Could not check alembic state: {str(e)}")
        return False

def stamp_database(revision='head'):
    """Stamp database with current revision without running migrations"""
    try:
        print(f"🏷️  Stamping database with revision: {revision}")
        result = subprocess.run(
            ["alembic", "stamp", revision],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        print("✅ Database stamped successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Stamp failed: {e.stderr}")
        return False

def run_migrations():
    """Run database migrations"""
    try:
        print("🔄 Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        print("✅ Migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e.stderr}")
        return False

def main():
    """Main initialization function"""
    db_initialized = check_database_initialized()
    alembic_initialized = check_alembic_initialized()

    if db_initialized and not alembic_initialized:
        # Tables exist but no alembic version - stamp the database
        print("📋 Tables exist but alembic not initialized, stamping database...")
        if not stamp_database('001'):
            return 1
    elif not db_initialized:
        # Database needs initialization
        print("📋 Initializing new database...")
        if not run_migrations():
            return 1
    else:
        # Database and alembic both initialized, run migrations to ensure up to date
        print("📋 Database initialized, checking for pending migrations...")
        if not run_migrations():
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
