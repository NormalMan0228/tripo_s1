# Checks what this PC has for Villagen development and what is still missing
# (docs/SHARE_GUIDE_KO.md). Reads nothing secret: key files are only checked for existence.
#   powershell -ExecutionPolicy Bypass -File tools/check_setup.ps1
$ErrorActionPreference = 'Continue'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskMissing = 0

function Report([string]$Name, [bool]$Ok, [string]$Detail, [string]$Fix, [switch]$Optional) {
    if ($Ok) { Write-Host ('[OK]   ' + $Name + '  ' + $Detail) -ForegroundColor Green; return }
    if ($Optional) { Write-Host ('[선택] ' + $Name + '  ' + $Fix) -ForegroundColor DarkYellow; return }
    Write-Host ('[없음] ' + $Name + '  ' + $Fix) -ForegroundColor Red
    $script:taskMissing++
}

function Version([string]$Command, [string[]]$Arguments) {
    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $found) { return '' }
    return ((& $found.Source @Arguments 2>$null) | Select-Object -First 1)
}

Write-Host '== 필수 (소스로 실행·개발)'
$git = Version 'git' @('--version')
Report 'Git' ([bool]$git) $git 'git-scm.com 에서 설치'
$uv = Version 'uv' @('--version')
Report 'uv (Python 관리)' ([bool]$uv) $uv 'PowerShell: winget install astral-sh.uv'
$python = Join-Path $taskRoot '.tools\server-venv\Scripts\python.exe'
$pythonOk = Test-Path -LiteralPath $python
Report 'Python 3.13 서버 환경' $pythonOk $(if ($pythonOk) { (& $python --version) } else { '' }) 'tools/setup.ps1 실행'
$godot = Join-Path $taskRoot '.tools\godot\Godot_v4.7.2-stable_win64_console.exe'
Report 'Godot 4.7.2' (Test-Path -LiteralPath $godot) '.tools\godot' 'godotengine.org 의 4.7.2-stable (Windows 64bit, .NET 아님)을 .tools\godot 에 풀기'
$assets = @('game\maps\archipelago\assets','game\assets\interior','game\assets\monsters','game\maps\survival\assets','game\assets\npc','game\assets\portraits')
$absent = @($assets | Where-Object { -not (Test-Path -LiteralPath (Join-Path $taskRoot $_)) })
Report '큰 에셋 폴더 (DevAssets)' ($absent.Count -eq 0) '6개 모두 있음' ('없음: ' + ($absent -join ', ') + ' → 팀에서 받은 개발용 에셋 묶음을 저장소 최상위에 풀기')

Write-Host ''
Write-Host '== 각자의 키 (서버를 직접 켤 때만)'
$tripo = if ($env:TRIPO_API_KEY_FILE) { $env:TRIPO_API_KEY_FILE } else { Join-Path $env:USERPROFILE 'Desktop\tripo_key.txt' }
Report 'Tripo 키 파일' (Test-Path -LiteralPath $tripo) $tripo ($tripo + ' 에 platform.tripo3d.ai 키 한 줄') -Optional
$gemini = if ($env:GEMINI_API_KEY_FILE) { $env:GEMINI_API_KEY_FILE } else { Join-Path $env:USERPROFILE 'Desktop\gemini_key.txt' }
Report 'Gemini 키 파일' (Test-Path -LiteralPath $gemini) $gemini ($gemini + ' 에 aistudio.google.com 키 한 줄') -Optional

Write-Host ''
Write-Host '== 선택 (필요한 사람만)'
Report 'Godot 내보내기 템플릿 4.7.2' (Test-Path -LiteralPath (Join-Path $taskRoot '.tools\godot-templates\windows_release_x86_64.exe')) '.tools\godot-templates' '게임 exe를 직접 만들 때: tools/setup.ps1 -Export' -Optional
$blender = Get-ChildItem -LiteralPath (Join-Path $taskRoot '.tools\blender-portable') -Directory -Filter 'blender-4.5*' -ErrorAction SilentlyContinue | Select-Object -First 1
Report 'Blender 4.5 LTS' ([bool]$blender) $(if ($blender) { $blender.Name } else { '' }) '아트·캐릭터 도구를 쓸 때: blender.org 4.5 LTS 포터블을 .tools\blender-portable 에 풀기' -Optional
Report '아트용 Python 환경' (Test-Path -LiteralPath (Join-Path $taskRoot '.tools\art-venv\Scripts\python.exe')) '.tools\art-venv' '아트 도구·배포 ZIP을 만들 때: tools/setup.ps1 -Art' -Optional
$tailscale = Get-Command 'tailscale' -ErrorAction SilentlyContinue
Report 'Tailscale' ([bool]$tailscale) '' '내 PC 서버에 친구를 부를 때: tailscale.com/download' -Optional
Report 'Inno Setup' (Test-Path -LiteralPath (Join-Path $taskRoot '.tools\innosetup\ISCC.exe')) '' '설치 파일(Setup.exe)을 만들 때만' -Optional

Write-Host ''
if ($taskMissing -eq 0) { Write-Host '필수 항목이 모두 준비됐습니다.' -ForegroundColor Green }
else { Write-Host ('필수 항목 ' + $taskMissing + '개가 없습니다. docs/SHARE_GUIDE_KO.md 를 보세요.') -ForegroundColor Red }
exit $taskMissing
