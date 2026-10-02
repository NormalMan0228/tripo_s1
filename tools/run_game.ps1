param([switch]$Editor, [switch]$Check)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskGodot = Get-ChildItem -LiteralPath (Join-Path $taskRoot '.tools\godot') -Filter '*_console.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $taskGodot) {
    throw 'Godot executable not found in .tools\godot. Open game\project.godot in Godot 4.7.2, or put the portable engine in .tools\godot.'
}
$taskArgs = @('--path', (Join-Path $taskRoot 'game'))
if ($Check) { $taskArgs += @('--headless', '--script', 'res://tests/smoke.gd') }
elseif ($Editor) { $taskArgs += '--editor' }
& $taskGodot.FullName @taskArgs
exit $LASTEXITCODE
