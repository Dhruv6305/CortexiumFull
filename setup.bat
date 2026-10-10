@echo off
title Cortexium 2.0 - Automated Setup Script
echo ===================================================
echo   CORTEXIUM 2.0 -- AUTOMATED SETUP & DEPENDENCY INSTALLER
echo ===================================================
echo.

:: 1. Create Python Virtual Environment
if not exist ".venv" (
    echo [+] Creating Python virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [+] Python virtual environment (.venv) already exists.
)

:: 2. Install Python Dependencies
echo [+] Installing Python dependencies into .venv...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r cortexium\requirements.txt

:: 3. Install Node.js / NPM Dependencies across all modules
echo.
echo [+] Installing Frontend Gateway Dashboard dependencies...
cd dashboard && call npm install && cd ..

echo [+] Installing Social Module dependencies...
cd frontend-web && call npm install && cd ..

echo [+] Installing Organizer Module dependencies...
cd cortexium-organizer-clone\frontend && call npm install && cd ..

echo [+] Installing Vehicle AR HUD Module dependencies...
cd cortexium-vehicle-web && call npm install && cd ..

echo.
echo ===================================================
echo   SETUP COMPLETE! ALL DEPENDENCIES INSTALLED.
echo ===================================================
echo.
echo You can now launch Cortexium 2.0 by double-clicking launch.bat or running:
echo   .\launch.bat
echo.
pause
