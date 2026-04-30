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
    echo Virtual environment created at .venv\
) else (
    echo Virtual environment already exists, reusing.
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q

:: Base packages
echo.
echo [1/4] Installing base packages...
pip install customtkinter pillow requests python-dotenv numpy ultralytics huggingface-hub opencv-python tipo-kgen -q
echo   Done.

:: PyTorch
echo.
echo [2/4] Installing PyTorch...
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
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 -q
) else if "%GPU_TYPE%" == "arc" (
    echo   Intel Arc ^(SYCL^) detected...
    pip install torch torchvision intel_extension_for_pytorch --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/us/ -q
) else (
    echo   No discrete GPU - CPU build...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q
)
echo   Done.

:: llama.cpp binary (TIPO backend)
echo.
echo [3/4] Downloading llama.cpp runtime (TIPO backend)...
if not exist "bin" mkdir bin
if not exist "bin\llama-cli.exe" (
    curl -L -o bin\llama.zip "https://github.com/ggml-org/llama.cpp/releases/download/b8929/llama-b8929-bin-win-cpu-x64.zip"
    powershell -Command "Expand-Archive -Path 'bin\llama.zip' -DestinationPath 'bin\llama_tmp' -Force"
    move /Y bin\llama_tmp\llama-cli.exe bin\llama-cli.exe >nul 2>&1
    copy /Y bin\llama_tmp\*.dll bin\ >nul 2>&1
    rmdir /S /Q bin\llama_tmp
    del bin\llama.zip
    echo   Done.
) else (
    echo   Already downloaded, skipping.
)

:: Create dirs
if not exist "models" mkdir models
if not exist "wildcards" mkdir wildcards
if not exist "output" mkdir output

echo.
echo ==============================
echo  Setup complete!
echo  Run the app:  run.bat
echo ==============================
pause
