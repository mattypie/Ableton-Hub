@echo off
REM Build Standalone Executable for Ableton Hub
REM This script uses PyInstaller to create a standalone .exe file

echo Building Ableton Hub executable...
echo.

REM Check if PyInstaller is installed
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

REM Get the directory where this batch file is located
cd /d "%~dp0"

REM Build the executable
python -m PyInstaller ^
    --name="Ableton Hub" ^
    --windowed ^
    --icon=resources/images/ableton-logo.png ^
    --add-data "resources;resources" ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=sqlalchemy ^
    --hidden-import=watchdog ^
    --hidden-import=zeroconf ^
    --collect-all=PyQt6 ^
    src/main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo Build complete! Executable is in the 'dist' folder.
echo You can now double-click 'Ableton Hub.exe' to run the application.
echo.
pause
