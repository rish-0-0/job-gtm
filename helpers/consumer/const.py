"""
Constants used by the helper enrichment consumer
"""
import os

# Enrichment pipeline configuration
ENRICHMENT_BATCH_SIZE = int(os.getenv("ENRICHMENT_BATCH_SIZE", "20"))
ENRICHMENT_BATCH_TIMEOUT = float(os.getenv("ENRICHMENT_BATCH_TIMEOUT", "3.0"))
OLLAMA_RATE_LIMIT = int(os.getenv("OLLAMA_RATE_LIMIT", "8"))
ENRICHMENT_MAX_RETRIES = int(os.getenv("ENRICHMENT_MAX_RETRIES", "3"))
