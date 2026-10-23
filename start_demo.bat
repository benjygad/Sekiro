@echo off
REM Run Sekiro Trainer in Demo Mode (no game needed)
echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   ⚔  Sekiro Trainer - DEMO MODE  ⚔  ║
echo  ║   Simulated data for testing          ║
echo  ╚═══════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

pip show pymem >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r "%~dp0requirements.txt"
)

echo Starting demo mode...
echo This shows the overlay with simulated game data.
echo Press F12 or Ctrl+C to quit.
echo.

python "%~dp0main.py" --demo %*
pause
