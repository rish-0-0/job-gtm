#!/bin/sh
set -e

echo "============================================"
echo "  Helper System - Ollama Model Initialization"
echo "============================================"
echo ""

echo "Waiting for Ollama service to be ready..."
while ! ollama list > /dev/null 2>&1; do
    echo "Ollama not ready yet, waiting..."
    sleep 2
done

echo "Ollama service is ready"

# Model to use (can be overridden via OLLAMA_MODEL env var)
MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
echo "Target model: $MODEL"

# Check if model is already pulled
if ollama list | grep -q "$MODEL"; then
    echo "$MODEL already exists"
else
    echo "Pulling $MODEL model (this may take a few minutes)..."
    ollama pull "$MODEL"
    echo "Model pulled successfully"
fi

echo ""
echo "Available models:"
ollama list

echo ""
echo "============================================"
echo "  Ollama initialization complete!"
echo "  Helper system ready to process jobs."
echo "============================================"
