@echo off
title Push Full Cortexium 2.0 to GitHub
echo ===================================================
echo   Pushing Full Cortexium Project to GitHub
echo ===================================================
echo.

:: 1. Clean nested .git folders so cortexium and organizer are included
echo [1/5] Removing nested .git submodules...
python prepare_push.py

:: Fallback removal via Windows commands
attrib -h -r -s "cortexium\.git\*.*" /s /d >nul 2>&1
rmdir /s /q "cortexium\.git" >nul 2>&1
attrib -h -r -s "cortexium-organizer-clone\.git\*.*" /s /d >nul 2>&1
rmdir /s /q "cortexium-organizer-clone\.git" >nul 2>&1

:: 2. Initialize / configure main Git repo
echo.
echo [2/5] Configuring Git repository...
git init
git branch -M main

:: Remove existing origin and re-add cleanly
git remote remove origin >nul 2>&1
git remote add origin https://github.com/Dhruv6305/CortexiumFull.git

:: 3. Clear cached submodule links so git sees actual files
echo.
echo [3/5] Unlinking submodule cache and staging all files...
git rm -r --cached cortexium >nul 2>&1
git rm -r --cached cortexium-organizer-clone >nul 2>&1
git add .

:: 4. Commit all files
echo.
echo [4/5] Creating commit...
git commit -m "Add full project: cortexium, cortexium-organizer-clone, dashboard, and backend"

:: 5. Push to GitHub
echo.
echo [5/5] Pushing to GitHub (https://github.com/Dhruv6305/CortexiumFull)...
git push -u origin main --force

echo.
echo ===================================================
echo   Upload complete!
echo   Check your repository at:
echo   https://github.com/Dhruv6305/CortexiumFull
echo ===================================================
pause
