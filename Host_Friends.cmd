@echo off
rem Hosts this PC's Tripo-enabled server for friends on your Tailscale network, then opens the game.
rem Install Tailscale and sign in first; the address to share is printed below.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\play_tripo.ps1" -Tailscale
pause
