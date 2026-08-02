@echo off
chcp 65001 >nul
title Imvoi AI OCR & VIP Receipt Manager
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo Starting Imvoi App via Virtual Environment...
    ".venv\Scripts\python.exe" main.py
) else (
    echo Starting Imvoi App via System Python...
    python main.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo App exited with an error code: %ERRORLEVEL%
    pause
)
