#!/bin/bash
set -e

echo "=== Explainer Video Generator — Setup ==="
echo ""

# Python deps
echo "1. Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "2. Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "   ⚠ Ollama not found. Install from https://ollama.com"
else
    echo "   ✓ Ollama found"
    echo "   Pulling gemma2:2b model (this may take a few minutes)..."
    ollama pull gemma2:2b || echo "   Could not pull model. Run manually: ollama pull gemma2:2b"
fi

echo ""
echo "3. Optional: Set HF_TOKEN for AI-generated images"
echo "   Get a free token at https://huggingface.co/settings/tokens"
echo "   export HF_TOKEN=hf_your_token_here"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Test run:"
echo "  python src/cli.py 'Explain how DNS works' --style whiteboard"
echo ""
echo "List all styles:"
echo "  python src/cli.py --list-styles"
