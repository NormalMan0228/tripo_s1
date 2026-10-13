# Saves the S3 upload key (profile from tools/download_host.json) into %USERPROFILE%\.aws\credentials.
# Run it yourself in a terminal; the secret is typed hidden and never printed or written anywhere else.
#   powershell -ExecutionPolicy Bypass -File tools\aws_upload_login.ps1
$ErrorActionPreference = 'Stop'
$cfg = Get-Content (Join-Path $PSScriptRoot 'download_host.json') -Raw | ConvertFrom-Json
$profileName = $cfg.profile

$keyId = (Read-Host 'Access key ID (AKIA...)').Trim()
$secure = Read-Host 'Secret access key (hidden)' -AsSecureString
$secret = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)).Trim()
if (-not $keyId -or -not $secret) { throw 'Both values are needed.' }

$dir = Join-Path $env:USERPROFILE '.aws'
New-Item -ItemType Directory -Force $dir | Out-Null
$file = Join-Path $dir 'credentials'
$lines = @()
if (Test-Path $file) {
    # Keep every other profile; drop the old copy of ours.
    $skip = $false
    foreach ($line in Get-Content $file) {
        if ($line -match '^\s*\[(.+)\]\s*$') { $skip = ($Matches[1] -eq $profileName) }
        if (-not $skip) { $lines += $line }
    }
}
$lines += "[$profileName]", "aws_access_key_id = $keyId", "aws_secret_access_key = $secret", "region = $($cfg.region)"
[IO.File]::WriteAllLines($file, $lines)
Write-Host "Saved profile [$profileName] in $file. Next: tools\publish_school_build.py setup"
