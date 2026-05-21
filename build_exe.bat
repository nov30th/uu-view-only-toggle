@echo off
title Build UU View-Only EXE
cd /d "%~dp0"

echo [1/2] Installing dependencies...
pip install -r requirements.txt pyinstaller -q

echo [2/2] Building single-file EXE...
python -m PyInstaller --onefile --windowed ^
    --name "UUViewOnly" ^
    --icon=app.ico ^
    uu_view_only.py

echo.
echo [OK] EXE built at: dist\UUViewOnly.exe
echo      You can distribute this single file independently.
pause
