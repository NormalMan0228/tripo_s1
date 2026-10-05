@echo off
cd /d "%~dp0"
echo 1 Krita layered texture
echo 2 Material Maker graph
echo 3 Blender village source
echo 4 Blender face and hand rig template
echo 5 Blender animated hand source
choice /c 12345 /m "Open tool"
if errorlevel 5 goto hand
if errorlevel 4 goto rig
if errorlevel 3 goto village
if errorlevel 2 goto material
start "Krita Texture" ".tools\krita-5.3.4\krita-x64-5.3.4\bin\krita.exe" "art\source\village_materials\timber_touchup.kra"
exit /b
:material
start "Material Maker" ".tools\material-maker-1.7\material_maker_1_7_windows\material_maker.exe" "art\source\village_materials\village_timber.ptex"
exit /b
:village
start "Blender Village" ".tools\blender-portable\blender-4.5.3-windows-x64\blender.exe" "art\source\village_art_20261003.blend"
exit /b
:rig
start "Blender Rig" ".tools\blender-portable\blender-4.5.3-windows-x64\blender.exe" "art\source\explorer_detail_rig_template.blend"
exit /b
:hand
start "Blender Hand" ".tools\blender-portable\blender-4.5.3-windows-x64\blender.exe" "art\source\open_hand_rigged_20261003.blend"
