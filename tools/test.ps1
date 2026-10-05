param([switch]$Capture, [switch]$Night, [switch]$Packaged, [switch]$Developer, [switch]$PortableServer, [switch]$EngineDiagnostics, [switch]$FullRun, [switch]$Combat, [switch]$Loss, [switch]$Expansion, [switch]$Village, [switch]$SkipServerTests, [string]$Region = 'forest', [string]$Difficulty = 'standard', [string]$Chapter = '', [string]$ClientScript = '', [string]$ClientPack = '')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
$taskGodot = Join-Path $taskRoot '.tools\godot\Godot_v4.7.2-stable_win64_console.exe'
$taskGameArguments = @('--path',(Join-Path $taskRoot 'game'),'--script','res://tests/integration.gd')
if ($Expansion) { $taskGameArguments = @('--path',(Join-Path $taskRoot 'game'),'--script','res://tests/expansion.gd') }
if ($Village) { $taskGameArguments = @('--path',(Join-Path $taskRoot 'game'),'--script','res://tests/village_life.gd') }
if ($FullRun) { $taskGameArguments = @('--path',(Join-Path $taskRoot 'game'),'--script','res://tests/seven_days.gd') }
if ($Combat) {
    if ($Packaged -or $FullRun) { throw 'Combat uses the source harness; run it separately.' }
    $taskGameArguments = @('--path',(Join-Path $taskRoot 'game'),'--script','res://tests/combat_play.gd')
}
if ($Packaged) {
    $taskGameArguments = @('--main-pack',(Join-Path $taskRoot 'builds\windows\Tripothon.pck'),'--script',(Join-Path $taskRoot 'game\tests\integration.gd'))
    if ($Expansion) { $taskGameArguments = @('--main-pack',(Join-Path $taskRoot 'builds\windows\Tripothon.pck'),'--script',(Join-Path $taskRoot 'game\tests\expansion.gd')) }
    if ($Village) { $taskGameArguments = @('--main-pack',(Join-Path $taskRoot 'builds\windows\Tripothon.pck'),'--script',(Join-Path $taskRoot 'game\tests\village_life.gd')) }
    if ($FullRun) { $taskGameArguments = @('--main-pack',(Join-Path $taskRoot 'builds\windows\Tripothon.pck'),'--script',(Join-Path $taskRoot 'game\tests\seven_days.gd')) }
}
if ($ClientScript) {
    if ($ClientScript -notmatch '^[a-z0-9_]+$') { throw 'ClientScript must be a test name without a path or extension.' }
    $taskScript = Join-Path $taskRoot ('game\tests\' + $ClientScript + '.gd')
    if (-not (Test-Path -LiteralPath $taskScript)) { throw 'Client test was not found.' }
    $taskGameArguments = @('--path',(Join-Path $taskRoot 'game'),'--script',('res://tests/' + $ClientScript + '.gd'))
    if ($Packaged) { $taskGameArguments = @('--main-pack',(Join-Path $taskRoot 'builds\windows\Tripothon.pck'),'--script',$taskScript) }
}
if ($EngineDiagnostics) { $taskGameArguments = @('--verbose') + $taskGameArguments }
if ($ClientPack) {
    if (-not $Packaged) { throw 'ClientPack requires Packaged.' }
    $taskSelectedPack = (Resolve-Path -LiteralPath $ClientPack).Path
    $taskGameArguments = @($taskGameArguments | ForEach-Object {
        if ($_ -eq (Join-Path $taskRoot 'builds\windows\Tripothon.pck')) { $taskSelectedPack } else { $_ }
    })
}
if ($Packaged -and $Developer) {
    $taskGameArguments = @($taskGameArguments | ForEach-Object {
        if ($_ -eq (Join-Path $taskRoot 'builds\windows\Tripothon.pck')) { Join-Path $taskRoot 'builds\windows\Tripothon_Developer.pck' } else { $_ }
    })
}
if ($Loss -and ($Combat -or $FullRun)) { throw 'Loss extends the standard integration test; run it without Combat/FullRun.' }
if (-not $SkipServerTests) {
    & $taskPython -m pytest server/tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Server tests failed' }
}
$taskOldData = $env:TRIPOTHON_DATA_DIR
$taskOldMode = $env:TRIPOTHON_MODE
$taskOldLimit = $env:TRIPO_DAILY_REQUEST_LIMIT
$env:TRIPOTHON_DATA_DIR = Join-Path $taskRoot ('artifacts\qa-' + [guid]::NewGuid().ToString('N'))
$env:TRIPOTHON_MODE = 'demo'
$env:TRIPO_DAILY_REQUEST_LIMIT = '100'
try {
    $taskServerExecutable = $taskPython
    $taskServerArguments = @('-m','uvicorn','server.app:create_app','--factory','--host','127.0.0.1','--port','8766','--workers','1','--no-access-log','--no-proxy-headers')
    if ($PortableServer) {
        $taskServerExecutable = Join-Path $taskRoot 'builds\TripothonDemoServer\TripothonDemoServer.exe'
        $taskServerArguments = @('--port','8766','--data-dir',('"' + $env:TRIPOTHON_DATA_DIR + '"'))
    }
    $taskServer = Start-Process -FilePath $taskServerExecutable -ArgumentList $taskServerArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'artifacts\qa-server.log' -RedirectStandardError 'artifacts\qa-server-error.log'
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        Start-Sleep -Milliseconds 200
        if ($taskServer.HasExited) { throw 'QA server failed to start' }
        try { $null = Invoke-RestMethod http://127.0.0.1:8766/health -TimeoutSec 1; break } catch {}
    }
    if ($Capture) {
        $taskArguments = $taskGameArguments + @('--','--capture','--mute',('--region=' + $Region),('--difficulty=' + $Difficulty),('--artifacts=' + (Join-Path $taskRoot 'artifacts')))
        if ($Night) { $taskArguments += '--night' }
        if ($Loss) { $taskArguments += '--loss' }
        if ($Chapter) { $taskArguments += ('--chapter=' + $Chapter) }
        if ($Developer) { $taskArguments += '--developer' }
        $taskProcess = Start-Process -FilePath $taskGodot -ArgumentList $taskArguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput 'artifacts\integration-render.log' -RedirectStandardError 'artifacts\integration-render-error.log'
        Get-Content artifacts\integration-render.log
        Get-Content artifacts\integration-render-error.log
        if ($taskProcess.ExitCode -ne 0) { throw 'Rendered integration failed' }
        if ((Get-Content artifacts\integration-render-error.log -Raw) -match '(?m)^\s*(SCRIPT ERROR|ERROR):') { throw 'Godot reported runtime errors during rendered integration.' }
    } else {
        $taskArguments = @('--headless') + $taskGameArguments + @('--','--mute',('--region=' + $Region),('--difficulty=' + $Difficulty))
        if ($Loss) { $taskArguments += '--loss' }
        if ($Chapter) { $taskArguments += ('--chapter=' + $Chapter) }
        if ($Developer) { $taskArguments += '--developer' }
        $taskProcess = Start-Process -FilePath $taskGodot -ArgumentList $taskArguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput 'artifacts\integration-headless.log' -RedirectStandardError 'artifacts\integration-headless-error.log'
        Get-Content artifacts\integration-headless.log
        Get-Content artifacts\integration-headless-error.log
        if ($taskProcess.ExitCode -ne 0) { throw 'Godot integration failed' }
        if ((Get-Content artifacts\integration-headless-error.log -Raw) -match '(?m)^\s*(SCRIPT ERROR|ERROR):') { throw 'Godot reported runtime errors during headless integration.' }
    }
} finally {
    if ($taskServer -and -not $taskServer.HasExited) { Stop-Process -Id $taskServer.Id; $taskServer.WaitForExit(5000) | Out-Null }
    # Each run uses a throwaway database; remove it so test accounts do not pile up.
    $taskQaData = $env:TRIPOTHON_DATA_DIR
    if ($taskQaData -and (Split-Path -Leaf $taskQaData) -like 'qa-*' -and (Test-Path -LiteralPath $taskQaData)) {
        Remove-Item -LiteralPath $taskQaData -Recurse -Force -ErrorAction SilentlyContinue
    }
    $env:TRIPOTHON_DATA_DIR = $taskOldData
    $env:TRIPOTHON_MODE = $taskOldMode
    $env:TRIPO_DAILY_REQUEST_LIMIT = $taskOldLimit
}
