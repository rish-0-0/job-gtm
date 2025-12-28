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

# Check if model is already pulled
if ollama list | grep -q "llama3.2:3b"; then
    echo "llama3.2:3b already exists"
else
    echo "Pulling llama3.2:3b model (this may take a few minutes)..."
    ollama pull llama3.2:3b
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
