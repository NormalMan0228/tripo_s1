param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Run tools\setup.ps1 first.'
}
& $taskPython -m uvicorn server.app:create_app --factory --host 127.0.0.1 --port $Port --workers 1 --no-access-log --no-proxy-headers
