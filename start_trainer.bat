@echo off
REM ============================================================
REM Sekiro Overlay Trainer - Windows Launcher
REM ============================================================
REM Run this script as Administrator for memory access.
REM ============================================================

title Sekiro Overlay Trainer
echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   ⚔  Sekiro Overlay Trainer  ⚔      ║
echo  ║   Perfect Parry Assistant            ║
echo  ╚═══════════════════════════════════════╝
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if running as admin (needed for memory access)
net session >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Not running as Administrator.
    echo Memory access may fail without admin privileges.
    echo Right-click this file and select "Run as administrator"
    echo.
    choice /C YN /M "Continue anyway?"
    if errorlevel 2 exit /b 0
    echo.
)

REM Check/install dependencies
echo Checking dependencies...
pip show pymem >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo.
echo Starting Sekiro Trainer...
echo Press F12 in-game to quit.
echo.

REM Run the trainer
python "%~dp0main.py" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Trainer exited with error.
    pause
)
