@echo off
:: ============================================================
:: DirectML training venv for AMD/Intel GPU on Windows
:: Requires Python 3.12 installed separately (not 3.14)
:: Download Python 3.12: https://www.python.org/downloads/
:: ============================================================
echo.
echo FlakAI - DirectML GPU Training Setup
echo =====================================
echo.

:: Check Python 3.12 is available
py -3.12 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3.12 not found.
    echo Install it from https://www.python.org/downloads/
    echo Make sure to check "Add to PATH" during installation.
    pause
    exit /b 1
)

py -3.12 --version

:: Create venv
echo Creating training_venv with Python 3.12...
py -3.12 -m venv "%~dp0training_venv"
if %errorlevel% neq 0 ( echo Failed to create venv. & pause & exit /b 1 )

:: Install packages
echo Installing PyTorch 2.2.0 + DirectML...
"%~dp0training_venv\Scripts\pip.exe" install --upgrade pip
"%~dp0training_venv\Scripts\pip.exe" install torch==2.2.0 torchvision==0.17.0 --index-url https://download.pytorch.org/whl/cpu
"%~dp0training_venv\Scripts\pip.exe" install torch-directml
"%~dp0training_venv\Scripts\pip.exe" install numpy pillow scikit-learn onnx

:: Test
echo.
echo Testing DirectML...
"%~dp0training_venv\Scripts\python.exe" -c "import torch_directml; print('DirectML OK:', torch_directml.device())"
if %errorlevel% neq 0 (
    echo DirectML test failed. Check GPU driver (needs AMD Software 22.11+).
    pause
    exit /b 1
)

:: Update trainer to use this venv
echo.
echo SUCCESS: DirectML venv ready at training\training_venv
echo.
echo To use GPU training, edit backend\ml\trainer.py:
echo   Change VENV_PYTHON to point to training\training_venv\Scripts\python.exe
echo   OR pass --device dml when calling training scripts directly
echo.
pause
