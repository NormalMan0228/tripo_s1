$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.tools/server-venv/Scripts/python.exe'
$taskGodot = Join-Path $taskRoot '.tools/godot/Godot_v4.7.2-stable_win64.exe'
Set-Location -LiteralPath $taskRoot
try { $taskHealth = Invoke-RestMethod 'http://127.0.0.1:8766/health' -TimeoutSec 2 } catch { $taskHealth = $null }
if ($taskHealth -and ($taskHealth.service -ne 'tripothon' -or $taskHealth.protocol -ne 6)) { throw 'Port 8766 is not a compatible Tripothon server.' }
if (-not $taskHealth) {
    $env:TRIPO_ENABLE_PAID = 'false'
    Remove-Item Env:TRIPO_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:TRIPO_API_KEY_FILE -ErrorAction SilentlyContinue
    & $taskPython tools/prepare_studio_review.py
    if ($LASTEXITCODE -ne 0) { throw 'Review seed failed' }
    $env:TRIPOTHON_DATA_DIR = Join-Path $taskRoot 'artifacts/studio-review-data'
    $env:TRIPOTHON_STUDIO_LLM = 'codex'
    $env:TRIPOTHON_MODE = 'demo'
    $env:TRIPO_ENABLE_PAID = 'false'
    $env:TRIPO_DAILY_REQUEST_LIMIT = '100'
    $taskLog = Join-Path $taskRoot 'artifacts/studio-server.log'
    $taskErrorLog = Join-Path $taskRoot 'artifacts/studio-server-error.log'
    $taskServer = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','server.app:create_app','--factory','--host','127.0.0.1','--port','8766','--no-access-log','--no-proxy-headers') -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskLog -RedirectStandardError $taskErrorLog
    $taskServer.Id | Set-Content (Join-Path $taskRoot 'artifacts/studio-server.pid')
    for ($taskAttempt = 0; $taskAttempt -lt 25; $taskAttempt++) {
        try { Invoke-RestMethod 'http://127.0.0.1:8766/health' -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Milliseconds 200 }
    }
}
Start-Process -FilePath $taskGodot -ArgumentList @('--path',(Join-Path $taskRoot 'game'),'--script','res://tests/studio_review.gd') -WindowStyle Normal
