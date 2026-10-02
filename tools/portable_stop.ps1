$ErrorActionPreference = 'Stop'
$taskPidFile = Join-Path $env:LOCALAPPDATA 'TripothonDemo\server.pid'
if (-not (Test-Path -LiteralPath $taskPidFile)) { Write-Output 'No portable server PID saved.'; exit }
$taskServerId = [int](Get-Content -LiteralPath $taskPidFile)
$taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$taskServerId"
$taskExpectedExe = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'server\TripothonDemoServer.exe'))
if ($taskProcess -and $taskProcess.ExecutablePath -eq $taskExpectedExe) {
    Stop-Process -Id $taskServerId
    Write-Output 'Portable demo server stopped. Saved data is preserved.'
} elseif ($taskProcess) { throw 'Saved PID belongs to another executable; refusing to stop it.' }
