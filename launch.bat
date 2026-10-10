@echo off
title Cortexium 2.0 - Master Launcher
echo ==========================================
echo    CORTEXIUM XR 2.0 -- MASTER LAUNCHER
echo ==========================================
echo.
echo   Frontend  : http://localhost:3020
echo   Backend   : http://localhost:4040
echo.

:: Clean up old processes
echo [+] Clearing previous sessions...
taskkill /f /im python.exe /t >nul 2>&1
taskkill /f /im node.exe /t >nul 2>&1

:: Check Ollama (optional - skip if not installed)
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Ollama not found - LLM will use fallback mode
    echo.
) else (
    echo [+] Ollama detected.
    ollama list | findstr "llama3" >nul
    if %errorlevel% equ 0 (echo [+] llama3 ready.) else (
        ollama list | findstr "mistral" >nul
        if %errorlevel% equ 0 (echo [+] mistral ready.) else (
            echo [!] Pulling llama3 in background...
            start "Ollama Setup" cmd /c "ollama pull llama3"
        )
    )
    echo.
)

:: ──────────────────────────────────────────────────────────
:: 1. Unified Backend  (Port 4040)
::    Serves:  /api/*         Social module routes
::             /organizer/*   Organizer module routes
:: ──────────────────────────────────────────────────────────
echo [1/6] Launching Unified Backend (Port 4040)...
start "Backend [4040]" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && python run_backend.py"

echo [+] Waiting 8s for backend to start...
timeout /t 8 /nobreak >nul

:: ──────────────────────────────────────────────────────────
:: 2. Social Module  (internal Port 3021)
::    Accessible at: http://localhost:3020/module/social
:: ──────────────────────────────────────────────────────────
echo [2/6] Launching Social Module (internal Port 3021)...
start "Social [:3021]" cmd /k "cd /d %~dp0frontend-web && npm run dev -- --port 3021"

:: ──────────────────────────────────────────────────────────
:: 3. Organizer Module  (internal Port 3022)
::    Accessible at: http://localhost:3020/module/organizer
:: ──────────────────────────────────────────────────────────
echo [3/6] Launching Organizer Module (internal Port 3022)...
start "Organizer [:3022]" cmd /k "cd /d %~dp0cortexium-organizer-clone\frontend && npm run dev -- --port 3022"

:: ──────────────────────────────────────────────────────────
:: 4. Vehicle Telemetry & 3D AR HUD Module  (internal Port 3023)
::    Accessible at: http://localhost:3020/module/vehicle
:: ──────────────────────────────────────────────────────────
echo [4/6] Launching Vehicle Telemetry & AR HUD Module (internal Port 3023)...
if not exist "%~dp0cortexium-vehicle-web\node_modules" (
    echo [+] Installing Vehicle Web dependencies...
    cmd /c "cd /d %~dp0cortexium-vehicle-web && npm install"
)
start "Vehicle [:3023]" cmd /k "cd /d %~dp0cortexium-vehicle-web && npm run dev -- --port 3023"

:: Wait for internal Vite servers to start
timeout /t 5 /nobreak >nul

:: ──────────────────────────────────────────────────────────
:: 5. Central Dashboard (public Port 3020) — opens the browser
::    This is the ONLY port users need.
::    Routes all module traffic through Vite proxy.
:: ──────────────────────────────────────────────────────────
echo [5/6] Launching Frontend Gateway (Port 3020)...
start "Dashboard [3020]" cmd /k "cd /d %~dp0dashboard && npm run dev -- --port 3020"

timeout /t 3 /nobreak >nul

:: ──────────────────────────────────────────────────────────
:: 6. Cloudflare Tunnel (Public HTTPS Website for Remote Laptops)
:: ──────────────────────────────────────────────────────────
echo [6/6] Launching Cloudflare Public HTTPS Tunnel...
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:3020 --protocol http2"
) else (
    start "Cloudflare Tunnel" cmd /k "npx cloudflared tunnel --url http://localhost:3020 --protocol http2"
)

echo.
echo ==========================================
echo    ALL SYSTEMS UP (3/3 MODULES ACTIVE)
echo ==========================================
echo.
echo   >> LOCAL BROWSER:     http://localhost:3020
echo   >> PUBLIC REMOTE HTTPS LINK WILL BE PRINTED IN THE
echo      'Cloudflare Tunnel' WINDOW ABOVE!
echo.
echo   Dashboard            http://localhost:3020
echo   Social Module        http://localhost:3020/module/social
echo   Organizer Module     http://localhost:3020/module/organizer
echo   Vehicle AR HUD       http://localhost:3020/module/vehicle
echo.
echo   Backend API          http://localhost:4040
echo   API Docs             http://localhost:4040/docs
echo   Vehicle Telemetry API http://localhost:4040/api/vehicle/status
echo.
echo   To change ports:     python change_ports.py
echo ==========================================
pause
