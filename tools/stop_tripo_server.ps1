$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPidFile = Join-Path $taskRoot 'artifacts\tripo-game-server.pid'
$taskPython = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPidFile)) { Write-Output 'No Tripo game server PID saved.'; exit }
$taskId = [int](Get-Content -LiteralPath $taskPidFile)
$taskParent = Get-CimInstance Win32_Process -Filter "ProcessId=$taskId" -ErrorAction SilentlyContinue
if (-not $taskParent) { Write-Output 'Tripo game server is already stopped.'; exit }
if ($taskParent.ExecutablePath -ne $taskPython -or $taskParent.CommandLine -notlike '*uvicorn*server.app:create_app*8765*') {
    throw 'Saved PID belongs to another process.'
}
$taskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$taskId" -ErrorAction SilentlyContinue
foreach ($taskChild in $taskChildren) {
    if ($taskChild.CommandLine -like ('*' + $taskPython + '*uvicorn*server.app:create_app*8765*')) {
        Stop-Process -Id $taskChild.ProcessId -ErrorAction SilentlyContinue
    }
}
if (Get-Process -Id $taskId -ErrorAction SilentlyContinue) {
    Stop-Process -Id $taskId -ErrorAction Stop
}
Write-Output 'Tripo game server stopped. Saved explorers and assets are retained.'
