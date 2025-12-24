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
    print("Waiting for postgres...", flush=True)
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
                print("PostgreSQL is ready!", flush=True)
                return True
        except Exception as e:
            pass

        time.sleep(1)
        attempt += 1

    print("ERROR: PostgreSQL failed to become ready", flush=True)
    return False

def init_database():
    """Initialize database and run migrations"""
    print("Initializing database...", flush=True)
    try:
        result = subprocess.run(
            ["python", "init_db.py"],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Database initialization failed: {e}", flush=True)
        return False

def start_application():
    """Start the FastAPI application"""
    print("Starting FastAPI application...", flush=True)
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

    # Initialize database and run migrations
    if not init_database():
        sys.exit(1)

    # Start application (Temporal worker runs in separate container)
    start_application()

if __name__ == "__main__":
    main()
