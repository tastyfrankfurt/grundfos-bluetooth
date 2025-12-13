#!/bin/bash

# Grundfos Bluetooth Integration Setup Script

set -e

echo "==================================="
echo "Grundfos Bluetooth Integration Setup"
echo "==================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "✓ uv is already installed"
fi

echo ""
echo "Creating virtual environment..."
uv venv

echo ""
echo "Installing dependencies..."
source .venv/bin/activate
uv pip install -e ".[dev]"

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Parse your btsnoop capture (if you haven't already):"
echo "   python3 parse_btsnoop.py"
echo ""
echo "3. Copy integration to Home Assistant:"
echo "   cp -r custom_components/grundfos_bluetooth ~/.homeassistant/custom_components/"
echo ""
echo "4. Restart Home Assistant and add the integration"
echo ""
echo "For more information, see:"
echo "- README.md - User documentation"
echo "- DEVELOPMENT.md - Development guide"
echo "- PROTOCOL.md - Protocol documentation"
echo ""
