$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
$taskGodot = Join-Path $taskRoot '.tools\godot\Godot_v4.7.2-stable_win64.exe'
New-Item -ItemType Directory -Path artifacts -Force | Out-Null
try { $taskHealth = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 2 } catch { $taskHealth = $null }
if ($taskHealth -and $taskHealth.service -ne 'tripothon') { throw 'Port 8765 belongs to an unrecognized server.' }
if ($taskHealth -and $taskHealth.protocol -ne 6) { throw 'An older Tripothon server is running. Stop it with its own package StopServer.cmd, or tools\stop_server.ps1 if started from source, then run Play.cmd again. Saved data is retained.' }
if (-not $taskHealth) {
    $taskServer = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','server.app:create_app','--factory','--host','127.0.0.1','--port','8765','--workers','1','--no-access-log','--no-proxy-headers') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot 'artifacts\server.log') -RedirectStandardError (Join-Path $taskRoot 'artifacts\server-error.log')
    $taskServer.Id | Set-Content (Join-Path $taskRoot 'artifacts\server.pid')
    for ($taskAttempt = 0; $taskAttempt -lt 20; $taskAttempt++) {
        Start-Sleep -Milliseconds 250
        try { $taskHealth = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 1; break } catch {}
    }
    if (-not $taskHealth) { throw 'Server failed to start. See artifacts\server-error.log.' }
}
Start-Process -FilePath $taskGodot -ArgumentList @('--path',(Join-Path $taskRoot 'game')) -WindowStyle Normal
