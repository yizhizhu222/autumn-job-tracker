@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys;sys.exit(not (sys.version_info >= (3,10)))" >nul 2>nul
if errorlevel 1 goto try_python
py -3 -X utf8 launcher.py %*
goto result
:try_python
python -c "import sys;sys.exit(not (sys.version_info >= (3,10)))" >nul 2>nul
if errorlevel 1 goto missing
python -X utf8 launcher.py %*
:result
if errorlevel 1 (
    echo Startup failed. Read the error above and the README troubleshooting section.
    pause
)
exit /b
:missing
echo Python 3.10 or newer is required for the source edition.
echo For the easiest setup, download the Windows ZIP from:
echo https://github.com/yizhizhu222/autumn-job-tracker/releases/latest
pause
