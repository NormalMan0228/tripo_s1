$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
& $taskPython -m PyInstaller --noconfirm --onedir --console --name TripothonDemoServer --paths $taskRoot --distpath builds --workpath .tools/pyinstaller-work --specpath .tools --add-data ($taskRoot + '/game/assets/sample_stool.glb:game/assets') --collect-submodules uvicorn --exclude-module pytest tools/demo_server.py
if ($LASTEXITCODE -ne 0) { throw 'Portable demo server build failed.' }
