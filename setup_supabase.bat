@echo off
title IMVOI - SUPABASE CLOUD DATABASE SETUP
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" setup_supabase.py
) else (
    python setup_supabase.py
)
pause
