#!/bin/bash
# NAI Studio - Launcher
cd "$(cd "$(dirname "$0")" && pwd)"

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run setup.sh first."
    exit 1
fi

source .venv/bin/activate
exec python main.py "$@"
