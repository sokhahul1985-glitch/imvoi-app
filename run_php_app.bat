@echo off
chcp 65001 >nul
title CMP Golden Mekong Commercial Service - Imvoi Web App
echo ========================================================
echo   CMP Golden Mekong Commercial Service - Web Server
echo ========================================================
echo.

where php >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] PHP found in PATH. Starting PHP Built-in Server on http://localhost:8000 ...
    cd /d "%~dp0php_app"
    start http://localhost:8000
    php -S localhost:8000
) else (
    echo [INFO] Starting Web Application Server on http://localhost:8000 ...
    cd /d "%~dp0"
    start http://localhost:8000
    if exist ".\.venv\Scripts\python.exe" (
        .\.venv\Scripts\python.exe server.py
    ) else (
        python server.py
    )
)

pause
