@echo off
rem Shows which programs and files this PC still needs (docs/SHARE_GUIDE_KO.md).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\check_setup.ps1"
pause
