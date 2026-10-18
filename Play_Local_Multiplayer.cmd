@echo off
cd /d "%~dp0"
".tools\server-venv\Scripts\python.exe" tools\local_multiplayer.py %*
if errorlevel 1 pause
