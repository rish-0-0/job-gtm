"""
Constants used across the workflow service
"""

# Scraping configuration
MAX_PAGES = 500  # Maximum number of pages to scrape per scraper
CONCURRENT_PAGES_PER_SCRAPER = 10  # Max concurrent page requests to avoid DDoS detection
BATCH_DELAY_SECONDS = 10  # Delay between batches to be respectful to servers

# Enrichment pipeline configuration
ENRICHMENT_BATCH_SIZE = 20  # Number of jobs to process per batch
ENRICHMENT_BATCH_TIMEOUT = 3.0  # Seconds to wait for batch collection
PUPPETEER_RATE_LIMIT = 2  # Max concurrent Puppeteer scraping sessions
OLLAMA_RATE_LIMIT = 10  # Max concurrent Ollama API calls
ENRICHMENT_MAX_RETRIES = 3  # Max retries before sending to DLQ
