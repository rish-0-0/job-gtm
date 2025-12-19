"""
Constants used across the workflow service
"""

# Scraping configuration
MAX_PAGES = 500  # Maximum number of pages to scrape per scraper
CONCURRENT_PAGES_PER_SCRAPER = 10  # Max concurrent page requests to avoid DDoS detection
BATCH_DELAY_SECONDS = 10  # Delay between batches to be respectful to servers
