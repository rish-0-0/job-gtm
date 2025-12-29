"""
Constants used by the helper enrichment consumer
"""
import os

# Enrichment pipeline configuration
ENRICHMENT_BATCH_SIZE = int(os.getenv("ENRICHMENT_BATCH_SIZE", "5"))  # Reduced from 20 to 5 for large models
ENRICHMENT_BATCH_TIMEOUT = float(os.getenv("ENRICHMENT_BATCH_TIMEOUT", "5.0"))  # Increased timeout
OLLAMA_RATE_LIMIT = int(os.getenv("OLLAMA_RATE_LIMIT", "2"))  # Reduced from 8 to 2 for qwen2.5:7b
ENRICHMENT_MAX_RETRIES = int(os.getenv("ENRICHMENT_MAX_RETRIES", "3"))
