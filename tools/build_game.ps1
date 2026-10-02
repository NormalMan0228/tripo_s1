$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskGodot = Join-Path $taskRoot '.tools\godot\Godot_v4.7.2-stable_win64_console.exe'
$taskTemplate = Join-Path $taskRoot '.tools\godot-templates\windows_release_x86_64.exe'
if (-not (Test-Path -LiteralPath $taskTemplate)) { throw 'Install the official Godot 4.7.2 Windows export template at .tools/godot-templates/windows_release_x86_64.exe.' }
New-Item -ItemType Directory -Path builds/windows -Force | Out-Null
& $taskGodot --headless --path game --export-release 'Windows Desktop'
if ($LASTEXITCODE -ne 0) { throw 'Godot export failed.' }
& $taskGodot --headless --path game --export-release 'Windows Developer'
if ($LASTEXITCODE -ne 0) { throw 'Godot developer export failed.' }
Write-Output 'Built builds/windows/Tripothon.exe and Tripothon_Developer.exe. A separate server is required.'
