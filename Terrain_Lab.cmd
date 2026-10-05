@echo off
cd /d "%~dp0"
start "Tripothon Terrain Lab" ".tools\godot\Godot_v4.7.2-stable_win64.exe" --path "labs\terrain_lab" -- --free-camera
