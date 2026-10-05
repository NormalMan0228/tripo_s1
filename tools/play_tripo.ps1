# -ServerOnly starts or reuses the Tripo-enabled server without opening a client.
# -Lan also accepts logins from other PCs on the same router (http://<this PC's
# LAN address>:8765). Windows may ask once to allow Python through the firewall.
# -Tailscale also serves friends on your Tailscale network at this PC's 100.x
# address; nothing listens on the public internet.
param([switch]$ServerOnly, [switch]$Lan, [switch]$Tailscale)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
$taskGame = Join-Path $taskRoot 'builds\windows\Tripothon_Developer.exe'
$taskBuilds = Join-Path $taskRoot 'builds'
$taskDataRoot = Join-Path $env:LOCALAPPDATA 'TripothonDemo'
$taskData = Join-Path $taskDataRoot 'server-data'
$taskKeyFile = Join-Path $env:USERPROFILE 'Desktop\tripo_key.txt'
$taskPidFile = Join-Path $taskRoot 'artifacts\tripo-game-server.pid'
Set-Location -LiteralPath $taskRoot

if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw 'Python server runtime is missing.' }
if (-not $ServerOnly -and -not (Test-Path -LiteralPath $taskGame -PathType Leaf)) { throw 'Godot game build is missing.' }
if (-not (Test-Path -LiteralPath $taskKeyFile -PathType Leaf)) { throw 'Server-side Tripo key file is missing.' }

# This read-only account request confirms the secret works without echoing it.
$taskCheckOutput = & $taskPython tools/check_tripo.py --key-file $taskKeyFile
if ($LASTEXITCODE -ne 0) { throw 'Tripo account check failed.' }
$taskCheck = $taskCheckOutput | ConvertFrom-Json
if ($taskCheck.status -ne 'ok') { throw ('Tripo account check: ' + $taskCheck.status) }

# -Lan opens the server to other PCs behind the same router. A PC that holds a
# public internet address would publish the server to everyone, so -Lan refuses.
$taskBind = '127.0.0.1'
$taskLanAddress = ''
if ($Lan) {
    $taskAddresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object { $_.IPAddress })
    $taskPublic = $taskAddresses | Where-Object { $_ -notmatch '^(127\.|169\.254\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' }
    if ($taskPublic) { throw ('This PC is connected straight to the internet (' + ($taskPublic -join ', ') + '). -Lan would publish the server publicly, so it is refused.') }
    $taskLanAddress = $taskAddresses | Where-Object { $_ -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' } | Select-Object -First 1
    if (-not $taskLanAddress) { throw 'No home network address was found for -Lan.' }
    $taskBind = '0.0.0.0'
}
$taskTailnetAddress = ''
if ($Tailscale) {
    $taskTailnetAddress = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -match '^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.' } |
        Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $taskTailnetAddress) { throw 'Tailscale is not connected on this PC. Install Tailscale, sign in, then run this again.' }
    $taskBind = '127.0.0.1,' + $taskTailnetAddress
}
$taskUrl = 'http://127.0.0.1:8765'
$taskHealth = $null
try { $taskHealth = Invoke-RestMethod ($taskUrl + '/health') -TimeoutSec 2 } catch {}
$taskManaged = $null
if (Test-Path -LiteralPath $taskPidFile) {
    $taskId = [int](Get-Content -LiteralPath $taskPidFile)
    $taskManaged = Get-CimInstance Win32_Process -Filter "ProcessId=$taskId" -ErrorAction SilentlyContinue
    if ($taskManaged -and ($taskManaged.ExecutablePath -ne $taskPython -or ($taskManaged.CommandLine -notlike '*uvicorn*server.app:create_app*8765*' -and $taskManaged.CommandLine -notlike '*serve_multi.py*8765*'))) {
        throw 'Saved server PID belongs to another process.'
    }
}
$taskReuse = $taskHealth -and $taskHealth.service -eq 'tripothon' -and $taskHealth.protocol -eq 6 -and $taskManaged
# A running server bound to the wrong interface is restarted with the requested one.
$taskSignature = if ($Tailscale) { '*serve_multi.py ' + $taskBind + ' 8765*' } else { '*--host ' + $taskBind + ' --port*' }
if ($taskReuse -and ($taskManaged.CommandLine -notlike $taskSignature)) {
    Stop-Process -Id $taskManaged.ProcessId -ErrorAction Stop
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        try { Invoke-RestMethod ($taskUrl + '/health') -TimeoutSec 1 | Out-Null; Start-Sleep -Milliseconds 100 } catch { break }
    }
    $taskHealth = $null
    $taskReuse = $false
}
if ($taskHealth -and -not $taskReuse) {
    if ($taskHealth.service -ne 'tripothon' -or $taskHealth.protocol -ne 6 -or $taskHealth.mode -ne 'demo') {
        throw 'Port 8765 is occupied by another or incompatible server.'
    }
    $taskPortablePidFile = Join-Path $taskDataRoot 'server.pid'
    if (-not (Test-Path -LiteralPath $taskPortablePidFile)) { throw 'The running demo server is not managed by this project.' }
    $taskPortableId = [int](Get-Content -LiteralPath $taskPortablePidFile)
    $taskPortableProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$taskPortableId" -ErrorAction SilentlyContinue
    # Any packaged sample server from this project's builds folder shares the same data directory.
    $taskPortablePath = if ($taskPortableProcess) { [string]$taskPortableProcess.ExecutablePath } else { '' }
    if (-not $taskPortableProcess -or -not $taskPortablePath.StartsWith($taskBuilds + '\',[StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $taskPortablePath) -ne 'TripothonDemoServer.exe') {
        throw 'The running demo server does not match the saved project process.'
    }
}

# A fresh backup protects existing explorers and furniture before source-server migrations.
if (-not $taskReuse -and (Test-Path -LiteralPath (Join-Path $taskData 'world.sqlite3'))) {
    $taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $taskBackup = Join-Path $taskRoot ('artifacts\backups\before-tripo-play-' + $taskStamp)
    & $taskPython tools/backup_server.py create --data-dir $taskData --destination $taskBackup
    if ($LASTEXITCODE -ne 0) { throw 'Existing game data could not be backed up.' }
}

# Restart only this packaged game's window and its verified portable server.
if (-not $ServerOnly) {
    Get-CimInstance Win32_Process -Filter "Name='Tripothon_Developer.exe'" |
        Where-Object { $_.ExecutablePath -eq $taskGame } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction Stop }
}
if ($taskHealth -and -not $taskReuse) {
    Stop-Process -Id $taskPortableId -ErrorAction Stop
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        try { Invoke-RestMethod ($taskUrl + '/health') -TimeoutSec 1 | Out-Null; Start-Sleep -Milliseconds 100 } catch { break }
    }
}

if (-not $taskReuse) {
    New-Item -ItemType Directory -Path (Join-Path $taskRoot 'artifacts') -Force | Out-Null
    $env:TRIPOTHON_DATA_DIR = $taskData
    $env:TRIPOTHON_MODE = 'demo'
    $env:TRIPOTHON_STUDIO_LLM = 'codex'
    $env:TRIPOTHON_DESIGN_FORMAT = 'classic'
    $env:TRIPO_API_KEY_FILE = $taskKeyFile
    Remove-Item Env:TRIPO_API_KEY -ErrorAction SilentlyContinue
    $env:TRIPO_ENABLE_PAID = 'true'
    $env:TRIPO_MODEL = 'v3.1-20260211'
    $env:TRIPO_DAILY_REQUEST_LIMIT = '5'
    $env:TRIPO_RESERVE_PER_JOB = '200'
    $taskArguments = if ($Tailscale) { @('tools/serve_multi.py',$taskBind,'8765') } else { @('-m','uvicorn','server.app:create_app','--factory','--host',$taskBind,'--port','8765','--workers','1','--no-access-log','--no-proxy-headers') }
    $taskServer = Start-Process -FilePath $taskPython -ArgumentList $taskArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot 'artifacts\tripo-game-server.log') -RedirectStandardError (Join-Path $taskRoot 'artifacts\tripo-game-server-error.log')
    $taskServer.Id | Set-Content -LiteralPath $taskPidFile
    $taskHealth = $null
    for ($taskAttempt=0; $taskAttempt -lt 40; $taskAttempt++) {
        Start-Sleep -Milliseconds 250
        if ($taskServer.HasExited) { throw 'Tripo-enabled game server exited during startup.' }
        try { $taskHealth = Invoke-RestMethod ($taskUrl + '/health') -TimeoutSec 1; break } catch {}
    }
}
if (-not $taskHealth -or $taskHealth.service -ne 'tripothon' -or $taskHealth.protocol -ne 6) {
    throw 'Tripo-enabled game server did not become ready.'
}

# The game process never needs the API key or its file path.
Remove-Item Env:TRIPO_API_KEY_FILE -ErrorAction SilentlyContinue
Remove-Item Env:TRIPO_API_KEY -ErrorAction SilentlyContinue
if ($Lan) { Write-Output ('Friends on the same router can log in at: http://' + $taskLanAddress + ':8765') }
if ($Tailscale) { Write-Output ('Friends on your Tailscale network can log in at: http://' + $taskTailnetAddress + ':8765') }
if ($ServerOnly) {
    Write-Output ('Tripo-enabled server is ready at http://127.0.0.1:8765. Available provider credits: ' + $taskCheck.available_credits)
    exit 0
}
Start-Process -FilePath $taskGame -WorkingDirectory (Split-Path -Parent $taskGame) -WindowStyle Normal
Write-Output ('Tripothon is running with server-side Tripo access. Available provider credits: ' + $taskCheck.available_credits)
