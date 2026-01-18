@echo off
REM Ableton Hub Launcher Script
REM This script allows you to double-click to run Ableton Hub

REM Get the directory where this batch file is located
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11 or later and ensure it's in your system PATH
    pause
    exit /b 1
)

REM Run the application
python -m src.main

REM If the application exits with an error, pause so the user can see the error message
if errorlevel 1 (
    pause
)
