param(
    [ValidateSet('gl_compatibility','forward_plus')][string]$Renderer = 'gl_compatibility',
    [int]$Runs = 1,
    [switch]$Cold,
    [string]$Server = 'http://127.0.0.1:8824',
    [string]$Label = '',
    [string]$Exe = '',
    [string]$Pack = '',
    [switch]$StopAtTitle,
    [string]$GameArgs = ''
)
# Loading measurement (game/tests/loading_frames.gd with --load-phases) in a window on the test
# monitor, against a QA server you started (never the school or production server).
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\measure_loading.ps1 -Renderer forward_plus -Runs 3
# User data is isolated: the game runs with APPDATA and LOCALAPPDATA pointing at
# artifacts\loading\appdata-<label> (Godot keeps user:// there: settings, shader caches, patches; the
# NVIDIA driver puts its shader caches under it too), so the player's own settings and caches are
# neither read nor touched. Runs of one label share the folder (warm caches after the first);
# -Cold empties it before the first run (Godot's and the driver's shader caches cold).
# -Exe/-Pack measure an exported build: -Exe builds\windows\Villagen.exe -Pack builds\windows\Villagen.pck.
# Writes artifacts\loading\<label>[-cold]-<n>.json: the test's LOADING_FRAMES result plus the game
# process's peak working set and private bytes.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$godot = Join-Path $root '.tools\godot\Godot_v4.7.2-stable_win64_console.exe'
$out = Join-Path $root 'artifacts\loading'
New-Item -ItemType Directory -Force $out | Out-Null
if (-not $Label) { $Label = $Renderer + $(if ($Pack) { '-export' } else { '' }) }
$position = & (Join-Path $PSScriptRoot 'test_window_position.ps1')
$oldAppData = $env:APPDATA
$oldLocal = $env:LOCALAPPDATA
$appData = Join-Path $out ('appdata-' + $Label)
if ($Cold -and (Test-Path -LiteralPath $appData)) { Remove-Item -LiteralPath $appData -Recurse -Force }
New-Item -ItemType Directory -Force $appData | Out-Null
try {
    for ($run = 1; $run -le $Runs; $run++) {
        $env:APPDATA = $appData
        $env:LOCALAPPDATA = $appData
        $tag = $Label + $(if ($Cold -and $run -eq 1) { '-cold' } else { '' }) + '-' + $run
        $arguments = @()
        if ($position) { $arguments += @('--position', $position) }
        if ($Renderer -ne 'gl_compatibility') { $arguments += @('--rendering-method', $Renderer) }
        $program = $godot
        if ($Pack) {
            if ($Exe) { $program = (Resolve-Path -LiteralPath $Exe).Path }
            $arguments += @('--main-pack', (Resolve-Path -LiteralPath $Pack).Path, '--script', (Join-Path $root 'game\tests\loading_frames.gd'))
        } else {
            $arguments += @('--path', (Join-Path $root 'game'), '--script', 'res://tests/loading_frames.gd')
        }
        $arguments += @('--', ('--server=' + $Server), '--load-phases', '--mute')
        if ($StopAtTitle) { $arguments += '--stop-at-title' }
        if ($GameArgs) { $arguments += $GameArgs.Split(' ') }
        $log = Join-Path $out ($tag + '.log')
        $process = Start-Process -FilePath $program -ArgumentList $arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError ($log + '.err')
        # The console Godot is a small wrapper that starts the game as its child: measure both.
        $peak = 0; $private = 0
        while (-not $process.HasExited) {
            try {
                $ids = @($process.Id) + @(Get-CimInstance Win32_Process -Filter ("ParentProcessId=" + $process.Id) | ForEach-Object { $_.ProcessId })
                foreach ($id in $ids) {
                    $item = Get-Process -Id $id -ErrorAction SilentlyContinue
                    if ($item) { $peak = [math]::Max($peak, $item.PeakWorkingSet64); $private = [math]::Max($private, $item.PrivateMemorySize64) }
                }
            } catch {}
            Start-Sleep -Milliseconds 500
        }
        $line = Select-String -LiteralPath $log -Pattern '^LOADING_FRAMES ' | Select-Object -Last 1
        $result = if ($line) { $line.Line.Substring(15) | ConvertFrom-Json } else { [pscustomobject]@{ ok = $false; failures = @('no LOADING_FRAMES line') } }
        $result | Add-Member -NotePropertyName peak_working_set_mb -NotePropertyValue ([math]::Round($peak / 1MB)) -Force
        $result | Add-Member -NotePropertyName peak_private_mb -NotePropertyValue ([math]::Round($private / 1MB)) -Force
        $result | Add-Member -NotePropertyName renderer -NotePropertyValue $Renderer -Force
        $result | Add-Member -NotePropertyName cold -NotePropertyValue ([bool]($Cold -and $run -eq 1)) -Force
        $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $out ($tag + '.json')) -Encoding utf8
        Select-String -LiteralPath $log -Pattern '^LOADING ' | ForEach-Object { $_.Line }
        Write-Output ("{0}: ok={1} peak working set {2} MB, private {3} MB" -f $tag, $result.ok, $result.peak_working_set_mb, $result.peak_private_mb)
    }
} finally {
    $env:APPDATA = $oldAppData
    $env:LOCALAPPDATA = $oldLocal
}
