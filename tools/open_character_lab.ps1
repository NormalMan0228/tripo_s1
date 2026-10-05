param([switch]$Editor)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskEngine=Join-Path $taskRoot '.tools\godot\Godot_v4.7.2-stable_win64.exe'
$taskProject=Join-Path $taskRoot 'labs\character_lab'
$taskArgs=@('--path', ('"'+$taskProject+'"'))
if ($Editor) { $taskArgs += '--editor' }
# Visible window is intentional: the user requested a playable Godot test map.
Start-Process -FilePath $taskEngine -ArgumentList $taskArgs -WorkingDirectory $taskRoot
