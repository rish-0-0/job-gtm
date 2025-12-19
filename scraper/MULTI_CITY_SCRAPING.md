# Multi-City ZipRecruiter Scraping

## Overview

The ZipRecruiter scraper now supports scraping multiple Indian cities in parallel to maximize data collection speed.

## Registered Scrapers

Instead of a single `ziprecruiter` scraper, you now have 5 separate scrapers covering major Indian tech hubs:

1. `ziprecruiter-bengaluru` - Bengaluru (India's Silicon Valley)
2. `ziprecruiter-mumbai` - Mumbai (Financial capital)
3. `ziprecruiter-delhi` - Delhi (National capital)
4. `ziprecruiter-hyderabad` - Hyderabad (Major IT hub)
5. `ziprecruiter-pune` - Pune (Growing tech city)

Plus the existing scrapers:
- `dice`
- `simplyhired`

## How It Works

Each city scraper:
- Uses the same `ZipRecruiterScraper` class
- Configured with a specific city parameter
- Scrapes jobs from that city independently
- Logs include the city name: `[ZipRecruiterScraper-Bengaluru]`
- Can run in parallel with other city scrapers

## Running Scrapers

### Scrape All Cities (Recommended)

```bash
# Run workflow without specifying a scraper
# This will scrape ALL registered scrapers including all 5 Indian cities
curl -X POST http://localhost:8000/api/workflows/scrape \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 50}'
```

This will run:
- 5 ZipRecruiter city scrapers (Bengaluru, Mumbai, Delhi, Hyderabad, Pune)
- 1 Dice scraper
- 1 SimplyHired scraper

**Total: 7 scrapers running in parallel!**

### Scrape Specific City

```bash
# Scrape only Bengaluru
curl -X POST http://localhost:8000/api/workflows/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "max_pages": 50,
    "scraper_name": "ziprecruiter-bengaluru"
  }'
```

### Scrape Multiple Specific Cities

To scrape specific cities, you'll need to trigger multiple workflows:

```bash
# Bengaluru
curl -X POST http://localhost:8000/api/workflows/scrape \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 50, "scraper_name": "ziprecruiter-bengaluru"}'

# Mumbai
curl -X POST http://localhost:8000/api/workflows/scrape \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 50, "scraper_name": "ziprecruiter-mumbai"}'

# Delhi
curl -X POST http://localhost:8000/api/workflows/scrape \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 50, "scraper_name": "ziprecruiter-delhi"}'
```

## Performance

### Sequential (Before)
- 1 ZipRecruiter scraper
- Scrapes 1 city at a time
- Example: 500 pages × 1 city = 500 pages total
- Time: ~2-3 hours

### Parallel (After)
- 5 ZipRecruiter scrapers
- Scrapes 5 cities simultaneously
- Example: 500 pages × 5 cities = 2500 pages total
- Time: ~2-3 hours (same as before!)

**5x more data in the same amount of time!**

## Workflow Behavior

When you run the workflow:

1. **Temporal orchestrates** all scrapers concurrently
2. **Each city scraper** processes pages in batches (10 concurrent per scraper)
3. **Results published** to RabbitMQ queue as they're scraped
4. **Consumer processes** all results in batches of 50
5. **Database stores** jobs from all cities

## Monitoring

### Check Available Scrapers

```bash
curl http://localhost:6000/scrapers
```

You should see:
```json
{
  "scrapers": [
    "dice",
    "simplyhired",
    "ziprecruiter-bengaluru",
    "ziprecruiter-mumbai",
    "ziprecruiter-delhi",
    "ziprecruiter-hyderabad",
    "ziprecruiter-pune"
  ]
}
```

### View Logs by City

```bash
# Filter logs for specific city
docker logs temporal-scraper 2>&1 | grep "ZipRecruiterScraper-Bengaluru"
docker logs temporal-scraper 2>&1 | grep "ZipRecruiterScraper-Mumbai"
docker logs temporal-scraper 2>&1 | grep "ZipRecruiterScraper-Delhi"
```

## Adding More Cities

To add more cities, edit [scraper/src/scrapers/index.ts](src/scrapers/index.ts):

```typescript
const zipRecruiterCities = [
    "Bengaluru",
    "Mumbai",
    "Delhi",
    "Hyderabad",
    "Pune",
    // Add more cities here
    "Chennai",
    "Kolkata",
    "Gurugram"
];
```

Then rebuild the scraper service:

```bash
docker-compose up -d --build scraper
```

## Database Queries

All jobs are stored in the same table with their city in the `job_location` field:

```sql
-- Count jobs by city
SELECT job_location, COUNT(*) as job_count
FROM job_listings
WHERE scraper_source LIKE 'ziprecruiter-%'
GROUP BY job_location
ORDER BY job_count DESC;

-- Get jobs from specific city
SELECT * FROM job_listings
WHERE scraper_source = 'ziprecruiter-bengaluru'
LIMIT 10;

-- Total jobs from all ZipRecruiter cities
SELECT COUNT(*) FROM job_listings
WHERE scraper_source LIKE 'ziprecruiter-%';

-- Jobs by city
SELECT
    REPLACE(scraper_source, 'ziprecruiter-', '') as city,
    COUNT(*) as job_count
FROM job_listings
WHERE scraper_source LIKE 'ziprecruiter-%'
GROUP BY scraper_source
ORDER BY job_count DESC;
```

## Tips

1. **Run all cities together** for maximum efficiency
2. **Monitor RabbitMQ queue** to see messages flowing in
3. **Scale consumer** if queue depth grows: `docker-compose up -d --scale queue-consumer=3`
4. **Check Temporal UI** (localhost:8233) to monitor workflow progress
5. **Each city is independent** - if one fails, others continue

## Architecture Flow

```
Temporal Workflow (Multi-City India)
├── ziprecruiter-bengaluru (500 pages)  ─┐
├── ziprecruiter-mumbai (500 pages)      │
├── ziprecruiter-delhi (500 pages)       ├─→ RabbitMQ Queue
├── ziprecruiter-hyderabad (500 pages)   │       ↓
├── ziprecruiter-pune (500 pages)        │   Consumer
├── dice (500 pages)                     ├─→ (Batch: 50 msgs)
└── simplyhired (500 pages)              │       ↓
                                         └─→  Database
```

**Coverage:**
- 🇮🇳 Major Indian Tech Hubs: Bengaluru, Mumbai, Delhi, Hyderabad, Pune

All scrapers run in parallel, publishing to the queue, which the consumer processes efficiently in batches!
