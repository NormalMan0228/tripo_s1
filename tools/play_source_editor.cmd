@echo off
rem Runs the game from source with the Godot editor binary (for comparing against the exported Villagen.exe).
cd /d "%~dp0.."
start "" ".tools\godot\Godot_v4.7.2-stable_win64_console.exe" --path game
