@echo off
rem Opens the IME check window (game/tests/ime_probe.gd). Close it when done; the log goes to artifacts\ime-probe.txt.
cd /d "%~dp0.."
".tools\godot\Godot_v4.7.2-stable_win64_console.exe" --path game --resolution 800x620 --script res://tests/ime_probe.gd
