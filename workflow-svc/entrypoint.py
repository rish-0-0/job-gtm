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

def init_database():
    """Initialize database and run migrations"""
    print("Initializing database...")
    try:
        result = subprocess.run(
            ["python", "init_db.py"],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Database initialization failed: {e}")
        return False

def start_worker():
    """Start the Temporal worker in background"""
    print("Starting Temporal worker...")
    worker_process = subprocess.Popen(
        ["python", "worker.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Give worker a moment to start
    time.sleep(2)

    if worker_process.poll() is not None:
        print("ERROR: Worker failed to start")
        # Capture and print the error output
        stdout, stderr = worker_process.communicate()
        if stdout:
            print(f"Worker stdout: {stdout}")
        if stderr:
            print(f"Worker stderr: {stderr}")
        return None

    print("✅ Temporal worker started")
    return worker_process

def start_application():
    """Start the FastAPI application"""
    print("Starting FastAPI application...")
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

    # Start Temporal worker
    worker_process = start_worker()
    if worker_process is None:
        sys.exit(1)

    # Start application (this will replace the current process)
    # The worker runs in background
    start_application()

if __name__ == "__main__":
    main()
