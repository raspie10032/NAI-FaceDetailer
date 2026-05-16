#!/bin/bash
# NAI Studio - Setup (creates .venv and installs all dependencies)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== NAI Studio Setup ==="

# Python check (prefer python3, fall back to python)
PYTHON=$(command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10+ is required but not found."
    exit 1
fi

PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYMAJ=$($PYTHON -c "import sys; print(sys.version_info.major)")
PYMIN=$($PYTHON -c "import sys; print(sys.version_info.minor)")
echo "Found Python $PYVER"
if [ "$PYMAJ" -lt 3 ] || { [ "$PYMAJ" -eq 3 ] && [ "$PYMIN" -lt 10 ]; }; then
    echo "Error: Python 3.10+ required (found $PYVER)"
    exit 1
fi

# Create venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
else
    echo "Virtual environment already exists, reusing."
fi

PY=.venv/bin/python
"$PY" -m pip install --upgrade pip -q

OS=$(uname -s)

# ── [1/3] Base packages (single source: requirements.txt) ──────
echo ""
echo "[1/3] Installing base packages..."
"$PY" -m pip install -r requirements.txt -q
echo "  Done."

# ── [2/3] PyTorch (hardware-detected) ──────────────────────────
echo ""
echo "[2/3] Installing PyTorch..."
if [ "$OS" = "Darwin" ]; then
    echo "  macOS detected (Metal support)."
    "$PY" -m pip install torch torchvision -q
elif command -v nvcc &>/dev/null 2>&1 || nvidia-smi &>/dev/null 2>&1; then
    echo "  NVIDIA CUDA detected."
    "$PY" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 -q
elif command -v rocminfo &>/dev/null 2>&1; then
    echo "  AMD ROCm detected."
    "$PY" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.0 -q
elif command -v sycl-ls &>/dev/null 2>&1; then
    echo "  Intel Arc (SYCL) detected."
    "$PY" -m pip install torch torchvision intel_extension_for_pytorch \
        --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/us/ -q
else
    echo "  No GPU detected — CPU build."
    "$PY" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q
fi
echo "  Done."

# ── [3/3] llama-cpp-python (TIPO backend, CPU-only) ────────────
echo ""
echo "[3/3] Installing llama-cpp-python (TIPO backend)..."
"$PY" -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -q
echo "  Done."

mkdir -p models wildcards output

echo ""
echo "=============================="
echo " Setup complete!"
echo " Run the app:  bash run.sh"
echo "=============================="
