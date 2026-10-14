# Prepares this PC for running Villagen from source (docs/SHARE_GUIDE_KO.md).
#   -Godot  also downloads the official Godot 4.7.2 editor into .tools\godot
#   -Export also downloads the Windows export templates (needed to build Villagen.exe)
#   -Art    also creates .tools\art-venv for the art tools and release packaging
# -Godot/-Export read the download addresses from the git-ignored tools/third_party_downloads.local.json.
# Existing environments are kept and only topped up with the pinned packages.
param([switch]$Godot, [switch]$Export, [switch]$Art)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath '.tools\server-venv\Scripts\python.exe')) { uv venv .tools\server-venv --python 3.13 }
uv pip install --python .tools\server-venv\Scripts\python.exe -r server\requirements.txt pytest==9.1.1
if ($Godot -or $Export) {
    $taskArgs = @('tools\download_godot.py')
    if ($Export) { $taskArgs += '--templates' }
    & .tools\server-venv\Scripts\python.exe @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'Godot download failed.' }
}
if ($Art) {
    if (-not (Test-Path -LiteralPath '.tools\art-venv\Scripts\python.exe')) { uv venv .tools\art-venv --python 3.13 }
    uv pip install --python .tools\art-venv\Scripts\python.exe -r tools\requirements-art.txt
}
Write-Host 'Server runtime ready. Open game\project.godot with Godot 4.7.2.'
