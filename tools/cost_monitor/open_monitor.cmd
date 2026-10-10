@echo off
rem Villagen cost monitor: starts the local dashboard (127.0.0.1 only) if needed and opens it.
rem Settings and history: %LOCALAPPDATA%\Villagen\cost_monitor (never in the repository).
setlocal
set "MONITOR_PY=%~dp0..\..\.tools\server-venv\Scripts\python.exe"
if not exist "%MONITOR_PY%" (
  echo The server Python was not found: .tools\server-venv
  echo Run tools\setup.ps1 once in this checkout, then open the monitor again.
  pause
  exit /b 1
)
"%MONITOR_PY%" "%~dp0monitor.py" open
if errorlevel 1 pause
