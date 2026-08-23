#!/usr/bin/env bash
set -e

echo "🌙 Installing nightmux..."

if ! command -v pipx &> /dev/null; then
    echo "pipx is required but not installed. Installing pipx..."
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
fi

echo "Installing nightmux from PyPI..."
pipx install nightmux

echo "Running nightmux setup..."
nightmux --setup

echo "✅ Installation complete! Open Telegram to start using nightmux."
