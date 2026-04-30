#!/bin/bash
# NAI Studio - Setup (creates .venv and installs all dependencies)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== NAI Studio Setup ==="

# Python check
PYTHON=$(command -v python3.11)
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
    echo "Virtual environment created at .venv/"
else
    echo "Virtual environment already exists, reusing."
fi

source .venv/bin/activate
pip install --upgrade pip -q

OS=$(uname -s)
ARCH=$(uname -m)

# ── Base packages ──────────────────────────────────────────────
echo ""
echo "[1/4] Installing base packages..."
pip install customtkinter pillow requests python-dotenv numpy ultralytics huggingface-hub opencv-python tipo-kgen -q
echo "  Done."

# ── PyTorch ────────────────────────────────────────────────────
echo ""
echo "[2/4] Installing PyTorch..."
if [ "$OS" = "Darwin" ]; then
    echo "  macOS detected (Metal support)."
    pip install torch torchvision -q
elif command -v nvcc &>/dev/null 2>&1 || nvidia-smi &>/dev/null 2>&1; then
    CUDA_VER=$(nvcc --version 2>/dev/null | grep -oE 'release [0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+' | head -1)
    echo "  NVIDIA CUDA detected ($CUDA_VER)."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 -q
elif command -v rocminfo &>/dev/null 2>&1; then
    echo "  AMD ROCm detected."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.0 -q
elif command -v sycl-ls &>/dev/null 2>&1; then
    echo "  Intel Arc (SYCL) detected."
    pip install torch torchvision intel_extension_for_pytorch \
        --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/us/ -q
else
    echo "  No GPU detected — CPU build."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q
fi
echo "  Done."

# ── llama-cpp-python ───────────────────────────────────────────
echo ""
echo "[3/4] Installing llama-cpp-python (TIPO backend, CPU-only)..."
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -q
echo "  Done."

# Create models dir
mkdir -p models wildcards output

echo ""
echo "=============================="
echo " Setup complete!"
echo " Run the app:  bash run.sh"
echo "=============================="
