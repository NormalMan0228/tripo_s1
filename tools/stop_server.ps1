$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPidFile = Join-Path $taskRoot 'artifacts\server.pid'
if (-not (Test-Path -LiteralPath $taskPidFile)) { Write-Host 'No managed server PID.'; exit }
$taskServerId = [int](Get-Content -LiteralPath $taskPidFile)
$taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $taskServerId" -ErrorAction SilentlyContinue
if (-not $taskProcess) { Write-Host 'Server already stopped.'; exit }
if ($taskProcess.CommandLine -notlike '*uvicorn*server.app:create_app*' -or $taskProcess.CommandLine -notlike '*8765*') {
    throw 'PID no longer identifies the managed Tripothon server; no process was stopped.'
}
$taskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId = $taskServerId"
foreach ($taskChild in $taskChildren) {
    if ($taskChild.CommandLine -like '*uvicorn*server.app:create_app*' -and $taskChild.CommandLine -like '*8765*') {
        Stop-Process -Id $taskChild.ProcessId -ErrorAction SilentlyContinue
    }
}
Stop-Process -Id $taskServerId -ErrorAction SilentlyContinue
Write-Host 'Tripothon local server stopped. Saved data is retained.'
