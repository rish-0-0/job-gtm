# Ollama Setup Guide

## Overview

Ollama is now integrated into the docker-compose stack with GPU support and the Llama 3.2 3B parameter model pre-configured.

## Architecture

```
┌─────────────────────────────────────┐
│  ollama-llm (Main Service)          │
│  - GPU-enabled container            │
│  - Persistent model storage         │
│  - API endpoint: localhost:11434    │
└─────────────────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  ollama-init (One-time Setup)       │
│  - Pulls llama3.2:3b model          │
│  - Runs once then exits             │
│  - Checks if model exists first     │
└─────────────────────────────────────┘
```

## Prerequisites

### GPU Requirements

**NVIDIA GPU with Docker GPU support:**

1. **Install NVIDIA Container Toolkit:**
   ```bash
   # Ubuntu/Debian
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

2. **Verify GPU access:**
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

### Windows with WSL2

If you're on Windows (which appears to be your case):

1. **Install WSL2 with GPU support:**
   - Update to Windows 11 or Windows 10 version 21H2+
   - Install NVIDIA GPU drivers for Windows (not WSL)
   - Enable GPU support in Docker Desktop settings

2. **Verify in PowerShell:**
   ```powershell
   wsl --update
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

## Starting Ollama

### First Time Setup

```bash
# Start all services including Ollama
docker-compose up -d

# The ollama-init service will automatically:
# 1. Wait for ollama-llm to be healthy
# 2. Pull the llama3.2:3b model (~1.9GB download)
# 3. Exit when complete

# Check the initialization logs
docker logs ollama-init -f
```

### Verify Installation

```bash
# Check if Ollama is running
docker ps | grep ollama

# List available models
docker exec ollama-llm ollama list

# You should see:
# NAME              ID              SIZE      MODIFIED
# llama3.2:3b       a80c4f17acd5    2.0 GB    X minutes ago
```

## Using Ollama

### API Endpoint

Ollama API is available at: **http://localhost:11434**

### Test the Model

```bash
# Simple generation test
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Why is the sky blue?",
  "stream": false
}'

# Chat format test
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.2:3b",
  "messages": [
    {
      "role": "user",
      "content": "Hello! What can you help me with?"
    }
  ],
  "stream": false
}'
```

### Python Integration Example

```python
import requests
import json

def chat_with_llama(prompt: str) -> str:
    """Send a prompt to Ollama and get response"""
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(url, json=payload)
    result = response.json()

    return result.get("response", "")

# Example usage
answer = chat_with_llama("Explain what a job scraper does")
print(answer)
```

### JavaScript/TypeScript Integration Example

```typescript
async function chatWithLlama(prompt: string): Promise<string> {
    const response = await fetch('http://localhost:11434/api/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: 'llama3.2:3b',
            prompt: prompt,
            stream: false
        })
    });

    const data = await response.json();
    return data.response;
}

// Example usage
const answer = await chatWithLlama('What is TypeScript?');
console.log(answer);
```

## Model Information

**Llama 3.2 3B:**
- **Parameters:** 3 billion
- **Size:** ~2GB
- **Context Length:** 128K tokens
- **Use Cases:**
  - Job description analysis
  - Resume parsing
  - Text classification
  - Sentiment analysis
  - Entity extraction

## Managing Models

### Pull Additional Models

```bash
# Pull a different Llama model
docker exec ollama-llm ollama pull llama3.2:1b  # Smaller, faster

# Pull other models
docker exec ollama-llm ollama pull mistral:7b
docker exec ollama-llm ollama pull codellama:7b
```

### List Models

```bash
docker exec ollama-llm ollama list
```

### Remove Models

```bash
docker exec ollama-llm ollama rm llama3.2:3b
```

### Model Storage

Models are persisted in: `./data/ollama/`

This directory is mounted to the container, so models persist across container restarts.

## Troubleshooting

### GPU Not Detected

```bash
# Check if GPU is accessible
docker exec ollama-llm nvidia-smi

# If this fails, Docker doesn't have GPU access
# Reinstall NVIDIA Container Toolkit (see Prerequisites)
```

### Model Not Found

```bash
# Re-run the init container
docker-compose up ollama-init

# Or manually pull
docker exec ollama-llm ollama pull llama3.2:3b
```

### Out of Memory

If you get OOM errors with the 3B model:

```bash
# Try the smaller 1B model
docker exec ollama-llm ollama pull llama3.2:1b

# Or add memory limits to docker-compose.yml:
# Under ollama service:
#   deploy:
#     resources:
#       limits:
#         memory: 8G
```

### Init Container Keeps Restarting

The init container is set to `restart: "no"` so it only runs once. If it's failing:

```bash
# Check logs
docker logs ollama-init

# Common issues:
# 1. Ollama service not healthy yet - wait 30s after startup
# 2. Network issues - check internet connection
# 3. Disk space - ensure you have 3GB+ free
```

## API Documentation

Full Ollama API docs: https://github.com/ollama/ollama/blob/main/docs/api.md

**Key endpoints:**
- `POST /api/generate` - Generate text from prompt
- `POST /api/chat` - Chat completion (like ChatGPT)
- `GET /api/tags` - List models
- `POST /api/pull` - Pull a model
- `POST /api/embeddings` - Generate embeddings

## Integration Ideas for Job-GTM

### 1. Job Description Enhancement

```python
# Enhance scraped job descriptions
enhanced = chat_with_llama(f"""
Improve this job description for SEO and clarity:

{raw_job_description}

Make it more professional and highlight key requirements.
""")
```

### 2. Job Classification

```python
# Classify job seniority
classification = chat_with_llama(f"""
Classify this job as: Entry Level, Mid Level, Senior, or Lead

Job Title: {job_role}
Description: {job_description}

Return only one of the four options.
""")
```

### 3. Skills Extraction

```python
# Extract skills from job description
skills = chat_with_llama(f"""
Extract technical skills from this job description:

{job_description}

Return as comma-separated list.
""")
```

### 4. Duplicate Detection (Semantic)

```python
# Use embeddings endpoint for similarity matching
# Helpful for cross-platform duplicate detection beyond URL matching
```

## Performance Notes

**With GPU (RTX 3060 or better):**
- Inference speed: ~50-100 tokens/second
- Latency: <1 second for short prompts

**Without GPU (CPU only):**
- Inference speed: ~5-10 tokens/second
- Latency: 3-10 seconds for short prompts

**Recommended for production:**
- Use GPU for real-time analysis
- Use CPU for batch processing (acceptable latency)

## Next Steps

1. ✅ Ollama is running with GPU
2. ✅ Llama 3.2 3B model is loaded
3. 🔲 Integrate with job scraping workflow
4. 🔲 Add LLM-based job description enhancement
5. 🔲 Implement semantic duplicate detection
6. 🔲 Add skills extraction pipeline
