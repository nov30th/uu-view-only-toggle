@echo off
title UU View-Only Toggle

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERR] Python not found. Please install Python 3.10+ and add it to PATH.
    echo       Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

python "%~dp0uu_view_only.py"

echo.
echo Script exited. Press any key to close...
pause >nul
