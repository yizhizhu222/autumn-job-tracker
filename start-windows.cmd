@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py --open %*
) else (
    python app.py --open %*
)
if errorlevel 1 (
    echo Install Python 3.10 or newer from python.org, then try again.
    pause
)
