@echo off
cd /d "%~dp0"
echo Preparing the local AI model. The first download needs internet access.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local-ai.ps1" -DownloadModel
if errorlevel 1 echo Setup did not complete. Install Ollama from https://ollama.com/download/windows and run this file again.
pause
