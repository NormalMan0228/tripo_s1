$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
uv venv .tools\server-venv --python 3.13
uv pip install --python .tools\server-venv\Scripts\python.exe -r server\requirements.txt pytest==9.1.1
Write-Host 'Server runtime ready. Open game\project.godot with Godot 4.7.2.'
