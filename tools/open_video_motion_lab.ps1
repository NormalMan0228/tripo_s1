$ErrorActionPreference = 'Stop'
$taskVideoRoot = Split-Path -Parent $PSScriptRoot
$taskVideoGodot = Join-Path $taskVideoRoot '.tools/godot/Godot_v4.7.2-stable_win64.exe'
$taskVideoLab = Join-Path $taskVideoRoot 'labs/video_motion_lab'
if (!(Test-Path -LiteralPath $taskVideoGodot)) { throw 'Godot executable is unavailable' }
Start-Process -FilePath $taskVideoGodot -ArgumentList @('--path', $taskVideoLab) -WorkingDirectory $taskVideoRoot -WindowStyle Normal
