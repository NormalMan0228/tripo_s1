@echo off
rem Puts a "Villagen cost monitor" icon on the desktop that runs open_monitor.cmd from this folder.
setlocal
set "MONITOR_PY=%~dp0..\..\.tools\server-venv\Scripts\python.exe"
if not exist "%MONITOR_PY%" (
  echo The server Python was not found: .tools\server-venv
  echo Run tools\setup.ps1 once in this checkout, then run this again.
  pause
  exit /b 1
)
"%MONITOR_PY%" "%~dp0monitor.py" shortcut
pause
