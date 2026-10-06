$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskDeveloper = $args -contains '-Developer'
$taskDataRoot = Join-Path $env:LOCALAPPDATA 'TripothonDemo'
New-Item -ItemType Directory -Path $taskDataRoot -Force | Out-Null
$taskServerExe = Join-Path $taskRoot 'server\TripothonDemoServer.exe'
try { $taskHealth = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 2 } catch { $taskHealth = $null }
if ($taskHealth -and ($taskHealth.service -ne 'tripothon' -or $taskHealth.mode -ne 'demo')) { throw 'Port 8765 belongs to another service. Close it before starting this demo.' }
if ($taskHealth -and $taskHealth.protocol -ne 6) { throw 'An older Tripothon server is running. Stop that server using its own StopServer.cmd (or source tools\stop_server.ps1), then start this demo again. Saved data is retained.' }
if (-not $taskHealth) {
    $taskServer = Start-Process -FilePath $taskServerExe -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskDataRoot 'server.log') -RedirectStandardError (Join-Path $taskDataRoot 'server-error.log')
    $taskServer.Id | Set-Content (Join-Path $taskDataRoot 'server.pid')
    for ($taskAttempt=0; $taskAttempt -lt 40; $taskAttempt++) {
        Start-Sleep -Milliseconds 250
        if ($taskServer.HasExited) { throw ('Demo server stopped. See '+$taskDataRoot+'\server-error.log') }
        try { $taskHealth = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 1; break } catch {}
    }
    if (-not $taskHealth) { throw 'Demo server did not become ready.' }
}
$taskClientName = if ($taskDeveloper) { 'Villagen_Developer.exe' } else { 'Villagen.exe' }
Start-Process -FilePath (Join-Path $taskRoot $taskClientName) -ArgumentList '--local-demo' -WorkingDirectory $taskRoot -WindowStyle Normal
