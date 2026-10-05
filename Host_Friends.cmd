@echo off
rem Hosts this PC's Tripo-enabled server for friends on the same router, then opens the game.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\play_tripo.ps1" -Lan
if errorlevel 1 pause
