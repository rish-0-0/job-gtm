#!/usr/bin/env python
"""
Entrypoint script for workflow-svc container
Handles database initialization and startup
"""
import subprocess
import sys
import time
import os

def wait_for_postgres():
    """Wait for PostgreSQL to be ready"""
    print("Waiting for postgres...")
    max_attempts = 60
    attempt = 0

    while attempt < max_attempts:
        try:
            result = subprocess.run(
                ["pg_isready", "-h", "postgres", "-p", "5432", "-U", "jobgtm"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("PostgreSQL is ready!")
                return True
        except Exception as e:
            pass

        time.sleep(1)
        attempt += 1

    print("ERROR: PostgreSQL failed to become ready")
    return False

def run_init_setup():
    """Run initial setup if needed"""
    print("Checking initial setup...")
    try:
        result = subprocess.run(
            ["python", "init_setup.py"],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Initial setup failed: {e}")
        return False

def run_migrations():
    """Run database migrations"""
    print("Running database migrations...")
    try:
        result = subprocess.run(
            ["python", "migrate.py"],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Migrations failed: {e}")
        return False

def start_application():
    """Start the FastAPI application"""
    print("Starting application...")
    port = os.getenv("PORT", "8000")

    # Use os.execvp to replace the current process
    os.execvp("python", [
        "python",
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        "0.0.0.0",
        "--port",
        port
    ])

def main():
    """Main entrypoint function"""
    # Wait for PostgreSQL
    if not wait_for_postgres():
        sys.exit(1)

    # Run initial setup
    if not run_init_setup():
        sys.exit(1)

    # Run migrations
    if not run_migrations():
        sys.exit(1)

    # Start application
    start_application()

if __name__ == "__main__":
    main()
