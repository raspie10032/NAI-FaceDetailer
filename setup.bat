@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0"
echo === NAI Studio Setup (Windows) ===

:: Python check
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Install Python 3.10+ from python.org
    pause & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Found Python %PYVER%

:: Create venv
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
) else (
    echo Virtual environment already exists, reusing.
)

set PY=.venv\Scripts\python.exe
"%PY%" -m pip install --upgrade pip -q

:: [1/3] Base packages (single source: requirements.txt)
echo.
echo [1/3] Installing base packages...
"%PY%" -m pip install -r requirements.txt -q
echo   Done.

:: [2/3] PyTorch (hardware-detected)
echo.
echo [2/3] Installing PyTorch...
set GPU_TYPE=cpu
nvidia-smi >nul 2>&1
if %errorlevel% == 0 (
    set GPU_TYPE=nvidia
) else (
    sycl-ls >nul 2>&1
    if %errorlevel% == 0 set GPU_TYPE=arc
)

if "%GPU_TYPE%" == "nvidia" (
    echo   NVIDIA GPU detected - CUDA build...
    "%PY%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 -q
) else if "%GPU_TYPE%" == "arc" (
    echo   Intel Arc ^(SYCL^) detected...
    "%PY%" -m pip install torch torchvision intel_extension_for_pytorch --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/us/ -q
) else (
    echo   No discrete GPU - CPU build...
    "%PY%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q
)
echo   Done.

:: [3/3] llama-cpp-python (TIPO backend, CPU-only) — the app imports
::       `llama_cpp`, so the Python package is required (not a binary).
echo.
echo [3/3] Installing llama-cpp-python (TIPO backend)...
"%PY%" -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -q
echo   Done.

:: Create runtime dirs
if not exist "models" mkdir models
if not exist "wildcards" mkdir wildcards
if not exist "output" mkdir output

echo.
echo ==============================
echo  Setup complete!
echo  Run the app:  run.bat
echo ==============================
pause
