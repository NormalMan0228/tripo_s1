@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\run_face_blender.ps1" -Open -BlendFile "%~dp0art\characters\explorer_b_pipeline_v3\01_template_test\mpfb_template_face_test.blend"
