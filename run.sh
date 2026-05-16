#!/bin/bash
# NAI Studio - Launcher
cd "$(cd "$(dirname "$0")" && pwd)"

if [ ! -x ".venv/bin/python" ]; then
    echo "Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Call the venv interpreter directly — no activation needed.
exec .venv/bin/python main.py "$@"
