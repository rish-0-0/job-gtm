FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Fix line endings and make start script executable
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Expose port
EXPOSE 8001

# Run migrations and start the application
CMD ["./start.sh"]
