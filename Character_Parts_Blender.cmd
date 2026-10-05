@echo off
setlocal
set "TASK_ROOT=%~dp0"
start "" "%TASK_ROOT%.tools\blender-portable\blender-4.5.3-windows-x64\blender.exe" "%TASK_ROOT%art\source\explorer_b_parts_20261003.blend"
