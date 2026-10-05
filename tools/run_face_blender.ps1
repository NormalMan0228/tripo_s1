param([string]$Script, [string]$BlendFile, [switch]$Open)
$ErrorActionPreference = 'Stop'
$faceWorkspace = Split-Path -Parent $PSScriptRoot
$faceProfile = Join-Path $faceWorkspace '.tools/blender-profiles/face-v3'
foreach ($folder in @('config','extensions','scripts','datafiles')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $faceProfile $folder) | Out-Null
}
$env:BLENDER_USER_CONFIG = Join-Path $faceProfile 'config'
$env:BLENDER_USER_EXTENSIONS = Join-Path $faceProfile 'extensions'
$env:BLENDER_USER_SCRIPTS = Join-Path $faceProfile 'scripts'
$env:BLENDER_USER_DATAFILES = Join-Path $faceProfile 'datafiles'
$faceBlender = Join-Path $faceWorkspace '.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe'
$faceArguments = @()
if (-not $Open) { $faceArguments += '--background' }
if ($BlendFile) { $faceArguments += $BlendFile }
if ($Script) { $faceArguments += @('--python-exit-code','1','--python',$Script) }
if ($Open) {
    # This foreground window is the user-facing test scene, not a background helper.
    Start-Process -FilePath $faceBlender -ArgumentList ($faceArguments | ForEach-Object { '"' + $_ + '"' })
} else {
    & $faceBlender @faceArguments
    exit $LASTEXITCODE
}
