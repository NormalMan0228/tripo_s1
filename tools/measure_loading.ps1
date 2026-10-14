param(
    [ValidateSet('gl_compatibility','forward_plus')][string]$Renderer = 'gl_compatibility',
    [int]$Runs = 1,
    [switch]$Cold,
    [string]$Server = 'http://127.0.0.1:8824',
    [string]$Label = '',
    [string]$Exe = '',
    [string]$Pack = '',
    [switch]$StopAtTitle,
    [string]$GameArgs = '',
    [string]$GameDir = '',
    [int]$First = 1
)
# Loading measurement (game/tests/loading_frames.gd with --load-phases) in a window on the test
# monitor, against a QA server you started (never the school or production server).
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\measure_loading.ps1 -Renderer forward_plus -Runs 3
# User data is isolated: the game runs with APPDATA and LOCALAPPDATA pointing at
# artifacts\loading\appdata-<label> (Godot keeps user:// there: settings, shader caches, patches; the
# NVIDIA driver puts its shader caches under it too), so the player's own settings and caches are
# neither read nor touched. Runs of one label share the folder (warm caches after the first);
# -Cold empties it before the first run (Godot's and the driver's shader caches cold).
# Exported builds: -Pack builds\windows\Villagen.pck runs it in the editor binary (--main-pack);
# -Exe builds\windows\Villagen.exe runs the exported game itself (its .pck beside it).
# -GameDir runs another copy of the project (e.g. an older commit for interleaved before/after runs).
# Writes artifacts\loading\<label>[-cold]-<n>.json: the test's LOADING_FRAMES result plus the game
# process's peak working set and private bytes.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$godot = Join-Path $root '.tools\godot\Godot_v4.7.2-stable_win64_console.exe'
$out = Join-Path $root 'artifacts\loading'
New-Item -ItemType Directory -Force $out | Out-Null
if (-not $Label) { $Label = $Renderer + $(if ($Pack -or $Exe) { '-export' } else { '' }) }
$position = & (Join-Path $PSScriptRoot 'test_window_position.ps1')
$oldAppData = $env:APPDATA
$oldLocal = $env:LOCALAPPDATA
$appData = Join-Path $out ('appdata-' + $Label)
if ($Cold -and (Test-Path -LiteralPath $appData)) { Remove-Item -LiteralPath $appData -Recurse -Force }
New-Item -ItemType Directory -Force $appData | Out-Null
if ($Exe -or $Pack) {
    # An exported game opens on the online world and asks it first whether this version may play:
    # point it at the QA server instead (never the school or the judges' server).
    $userDir = Join-Path $appData ('Godot\app_userdata\Tripothon ' + [char]0x2014 + ' Seven Nights')
    New-Item -ItemType Directory -Force $userDir | Out-Null
    $settings = Join-Path $userDir 'settings.cfg'
    $text = if (Test-Path -LiteralPath $settings) { Get-Content -LiteralPath $settings -Raw } else { '' }
    $line = 'server="' + $Server + '"'
    if ($text -notmatch '(?m)^server=') {
        if ($text -match '(?m)^\[game\]') { $text = $text -replace '(?m)^\[game\][^\r\n]*', ("[game]`r`n" + $line) }
        else { $text = $text + "`r`n[game]`r`n" + $line + "`r`n" }
        [System.IO.File]::WriteAllText($settings, $text, (New-Object System.Text.UTF8Encoding($false)))
    }
}
try {
    for ($run = $First; $run -lt $First + $Runs; $run++) {
        $env:APPDATA = $appData
        $env:LOCALAPPDATA = $appData
        $tag = $Label + $(if ($Cold -and $run -eq 1) { '-cold' } else { '' }) + '-' + $run
        $arguments = @()
        if ($position) { $arguments += @('--position', $position) }
        if ($Renderer -ne 'gl_compatibility') { $arguments += @('--rendering-method', $Renderer) }
        $program = $godot
        if ($Exe) {
            # The exported game itself (release template: it reads the .pck beside it; it runs neither
            # --main-pack nor test scripts): the start only, timed from its own --log-load lines
            # (BOOT card dressed, LOAD_FRAME, LOAD_TITLE); stopped once the title is up.
            $program = (Resolve-Path -LiteralPath $Exe).Path
            $arguments += @('--', '--log-load', '--mute')
            $log = Join-Path $out ($tag + '.log')
            $process = Start-Process -FilePath $program -ArgumentList $arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError ($log + '.err')
            $peak = 0; $private = 0; $deadline = (Get-Date).AddSeconds(180)
            while (-not $process.HasExited -and (Get-Date) -lt $deadline) {
                try { $process.Refresh(); $peak = [math]::Max($peak, $process.PeakWorkingSet64); $private = [math]::Max($private, $process.PrivateMemorySize64) } catch {}
                if (Select-String -LiteralPath $log -Pattern '^LOAD_TITLE' -Quiet) { Start-Sleep -Seconds 1; break }
                Start-Sleep -Milliseconds 500
            }
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force; $process.WaitForExit(5000) | Out-Null }
            $text = Get-Content -LiteralPath $log -Raw
            $card = [regex]::Match($text, 'BOOT card dressed (\d+) ms')
            $title = [regex]::Match($text, 'LOAD_TITLE (\d+) ms')
            $frames = @([regex]::Matches($text, 'LOAD_FRAME\s+([\d.]+) ms') | ForEach-Object { [double]$_.Groups[1].Value })
            $result = [pscustomobject]@{ ok = $title.Success; card_s = $(if ($card.Success) { [int]$card.Groups[1].Value / 1000.0 } else { $null });
                title_s = $(if ($title.Success) { [int]$title.Groups[1].Value / 1000.0 } else { $null });
                frames_over_50ms = $frames.Count; worst_ms = $(if ($frames.Count) { ($frames | Measure-Object -Maximum).Maximum } else { 0 });
                longest = @($frames | Sort-Object -Descending | Select-Object -First 5);
                peak_working_set_mb = [math]::Round($peak / 1MB); peak_private_mb = [math]::Round($private / 1MB); renderer = $Renderer; cold = [bool]($Cold -and $run -eq 1) }
            $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out ($tag + '.json')) -Encoding utf8
            Write-Output ("{0}: card {1} s, title {2} s, frames >50 ms under the card {3}, worst {4} ms, longest {5}" -f $tag, $result.card_s, $result.title_s, $result.frames_over_50ms, $result.worst_ms, ($result.longest -join ', '))
            continue
        } elseif ($Pack) {
            $arguments += @('--main-pack', (Resolve-Path -LiteralPath $Pack).Path, '--script', (Join-Path $root 'game\tests\loading_frames.gd'))
        } else {
            $arguments += @('--path', $(if ($GameDir) { (Resolve-Path -LiteralPath $GameDir).Path } else { Join-Path $root 'game' }), '--script', 'res://tests/loading_frames.gd')
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
