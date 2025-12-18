#!/usr/bin/env python
"""
Migration management script
Run this to apply database migrations
"""
import subprocess
import sys

def run_migrations():
    """Run Alembic migrations"""
    try:
        print("Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        print("✅ Migrations completed successfully")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e.stderr}")
        return 1

if __name__ == "__main__":
    sys.exit(run_migrations())
