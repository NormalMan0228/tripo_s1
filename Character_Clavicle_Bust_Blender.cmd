@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\run_face_blender.ps1" -Open -BlendFile "%~dp0art\characters\explorer_b_pipeline_v3\02_clavicle_bust\explorer_b_clavicle_bust_v1.blend"
