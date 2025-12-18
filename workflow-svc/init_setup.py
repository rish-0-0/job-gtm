#!/usr/bin/env python
"""
Automatic initial setup script
Creates the initial migration if none exists
"""
import subprocess
import sys
import os
from pathlib import Path

def has_migrations():
    """Check if any migration files exist"""
    versions_dir = Path("alembic/versions")
    if not versions_dir.exists():
        return False

    # Check for .py files (excluding __pycache__ and .gitkeep)
    migration_files = [
        f for f in versions_dir.glob("*.py")
        if f.name != "__init__.py" and not f.name.startswith(".")
    ]

    return len(migration_files) > 0

def create_initial_migration():
    """Create the initial migration using alembic"""
    try:
        print("📝 No migrations found. Creating initial schema migration...")

        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "initial schema"],
            check=True,
            capture_output=True,
            text=True
        )

        print(result.stdout)
        print("✅ Initial migration created successfully")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create initial migration: {e.stderr}")
        return False

def main():
    """Main setup function"""
    print("🔍 Checking for existing migrations...")

    if has_migrations():
        print("✅ Migrations already exist. Skipping initial setup.")
        return 0

    print("⚠️  No migrations found. Running initial setup...")

    if create_initial_migration():
        print("✅ Initial setup completed successfully")
        return 0
    else:
        print("❌ Initial setup failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
