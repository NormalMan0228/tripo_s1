@echo off
cd /d "%~dp0"
start "Tripothon Close Camera" ".tools\godot\Godot_v4.7.2-stable_win64.exe" --path "labs\village_art_lab" -- --closeup
