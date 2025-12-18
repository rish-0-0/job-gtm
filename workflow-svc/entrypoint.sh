#!/bin/bash
set -e

echo "Waiting for postgres..."
while ! pg_isready -h postgres -p 5432 -U jobgtm > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Checking initial setup..."
python init_setup.py

echo "Running database migrations..."
python migrate.py

echo "Starting application..."
exec python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
