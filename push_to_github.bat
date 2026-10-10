@echo off
title Push CortexiumFull to GitHub
echo ===================================================
echo   Pushing CortexiumFull to GitHub
echo ===================================================
echo.

git init
git branch -M main

:: Remove existing origin if already defined
git remote remove origin >nul 2>&1
git remote add origin https://github.com/Dhruv6305/CortexiumFull.git

echo [+] Staging project files (excluding virtual environments, node_modules, and >100MB videos)...
git add .

echo [+] Creating commit...
git commit -m "Initial commit: Cortexium XR 2.0 full multi-module platform"

echo [+] Pushing to main branch...
git push -u origin main

echo.
echo ===================================================
echo   Push complete!
echo   Repository: https://github.com/Dhruv6305/CortexiumFull
echo ===================================================
pause
