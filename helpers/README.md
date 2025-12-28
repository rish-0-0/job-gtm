# Helper System - Remote AI Enrichment Workers

This is a standalone helper system that can be deployed on a secondary laptop/machine to help speed up the job enrichment pipeline. It connects to the main system's RabbitMQ queue and uses a local Ollama instance for AI inference.

## Architecture

```
┌─────────────────────────────────────────┐
│ MAIN LAPTOP                             │
│                                         │
│  RabbitMQ (5672) ◄──────────────────────┼───┐
│       │                                 │   │
│       ├── raw_jobs_for_processing       │   │
│       │         ↓                       │   │
│       │   [Main Consumer]               │   │
│       │         ↓                       │   │
│       └── enriched_jobs ◄───────────────┼───┼──┐
│                 ↓                       │   │  │
│         Golden Job Consumer             │   │  │
│                 ↓                       │   │  │
│            PostgreSQL                   │   │  │
└─────────────────────────────────────────┘   │  │
                                              │  │
┌─────────────────────────────────────────┐   │  │
│ HELPER LAPTOP                           │   │  │
│                                         │   │  │
│  Ollama (llama3.2:3b)                   │   │  │
│       ↑                                 │   │  │
│  AI Enrichment Consumer ────────────────┼───┘  │
│       │                                 │      │
│       └─────────────────────────────────┼──────┘
│         (publishes enriched jobs)       │
└─────────────────────────────────────────┘
```

## Prerequisites

1. **Docker & Docker Compose** installed on the helper laptop
2. **NVIDIA GPU** with CUDA support (for Ollama acceleration)
3. **Network access** to the main laptop's RabbitMQ (port 5672)

## Setup Instructions

### Step 1: Configure the Main Laptop

Ensure RabbitMQ is accessible from the network:

1. Check that port 5672 is exposed in docker-compose.yml (it should be by default)
2. Get your main laptop's IP address:
   ```bash
   # Windows
   ipconfig
   # Look for "IPv4 Address" under your active network adapter

   # Linux/Mac
   ip addr
   # or
   ifconfig
   ```

### Step 2: Configure the Helper Laptop

1. Copy this `helpers` folder to your helper laptop

2. Copy the environment template and configure it:
   ```bash
   cd helpers
   cp .env.example .env
   ```

3. Edit `.env` and set your main laptop's IP address:
   ```bash
   RABBITMQ_URL=amqp://jobgtm:jobgtm_password@192.168.1.100:5672/
   ```

### Step 3: Start the Helper System

```bash
cd helpers
docker-compose up -d
```

This will:
1. Start the Ollama service
2. Pull the llama3.2:3b model (first run only, ~2GB download)
3. Start the AI enrichment consumer

### Step 4: Verify Operation

1. **Check logs:**
   ```bash
   docker-compose logs -f ai-enrichment-consumer
   ```

   You should see:
   ```
   ============================================================
     HELPER SYSTEM - AI Enrichment Consumer
   ============================================================

   Checking Ollama service health...
   Ollama service is healthy
   Connecting to remote RabbitMQ...
   Connected to queue: raw_jobs_for_processing

   ============================================================
     Ready to process jobs!
   ============================================================
   ```

2. **Check RabbitMQ Management UI** (on main laptop):
   - Open http://localhost:15672
   - Login: jobgtm / jobgtm_password
   - Go to "Queues" tab
   - Look at `raw_jobs_for_processing` - you should see an additional consumer

## Configuration Options

Edit `.env` to tune performance:

| Variable | Default | Description |
|----------|---------|-------------|
| `RABBITMQ_URL` | (required) | URL to main laptop's RabbitMQ |
| `CONSUMER_REPLICAS` | 1 | Number of consumer instances |
| `ENRICHMENT_BATCH_SIZE` | 20 | Jobs per batch |
| `OLLAMA_RATE_LIMIT` | 8 | Max concurrent Ollama calls from consumer |
| `OLLAMA_NUM_PARALLEL` | 8 | Max parallel requests Ollama handles |

### Performance Tuning (16GB VRAM with llama3.2:3b)

- **Default (8 parallel)**: Uses ~10GB VRAM, safe for 16GB
- **Conservative (5 parallel)**: Uses ~6GB VRAM, if you see OOM errors
- **Aggressive (10 parallel)**: Uses ~12GB VRAM, if you have headroom

Both `OLLAMA_RATE_LIMIT` and `OLLAMA_NUM_PARALLEL` should match.

## Commands

```bash
# Start the helper system
docker-compose up -d

# View logs
docker-compose logs -f

# View only consumer logs
docker-compose logs -f ai-enrichment-consumer

# Stop the helper system
docker-compose down

# Restart consumer (e.g., after config change)
docker-compose restart ai-enrichment-consumer

# Check Ollama status
docker exec helper-ollama ollama list
```

## Troubleshooting

### "Connection refused" to RabbitMQ

1. Check the IP address in `.env` is correct
2. Ensure both laptops are on the same network
3. Check firewall settings on the main laptop:
   ```bash
   # Windows: Allow port 5672 through Windows Firewall
   # Linux: sudo ufw allow 5672
   ```

### "No GPU detected" by Ollama

1. Ensure NVIDIA drivers are installed
2. Ensure nvidia-container-toolkit is installed:
   ```bash
   # Ubuntu/Debian
   sudo apt install nvidia-container-toolkit
   sudo systemctl restart docker
   ```

### Consumer not processing jobs

1. Check if there are jobs in the queue:
   - Open RabbitMQ Management UI
   - Check `raw_jobs_for_processing` queue message count

2. Check consumer logs for errors:
   ```bash
   docker-compose logs ai-enrichment-consumer
   ```

### Ollama running slow

1. Check GPU utilization:
   ```bash
   nvidia-smi
   ```

2. Reduce batch size and rate limit in `.env`:
   ```bash
   ENRICHMENT_BATCH_SIZE=10
   OLLAMA_RATE_LIMIT=5
   ```

## Files

```
helpers/
├── docker-compose.yml      # Main orchestration file
├── .env.example            # Configuration template
├── .env                    # Your configuration (create this)
├── README.md               # This file
├── init_scripts/
│   └── ollama-init.sh      # Model download script
├── consumer/
│   ├── Dockerfile          # Consumer container image
│   ├── requirements.txt    # Python dependencies
│   ├── ai_enrichment_consumer.py  # Main consumer
│   ├── ollama_client.py    # Ollama API client
│   ├── queue_config.py     # Queue configuration
│   └── const.py            # Constants
└── data/
    └── ollama/             # Ollama model storage (created on first run)
```
