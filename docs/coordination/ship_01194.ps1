$env:TRIPO_HEAVY_OWNER = '01'
Set-Location C:\lsm26\triphthonS1\.claude\worktrees\merge-vg
$sp = 'C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpad'
$py = '.tools\art-venv\Scripts\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File "$sp\build_01194.ps1"
if ($LASTEXITCODE -ne 0) { "BUILD STOPPED exit=$LASTEXITCODE"; exit 1 }
if (-not (Select-String -Path "$sp\b194_pck.log" -Pattern "PCK_CHECK b'ECFG' \d+ 0\.11\.9\.4" -Quiet)) { "PCK CHECK FAILED"; exit 2 }
& $py tools\publish_school_build.py upload *> "$sp\up0194.log"
"upload exit=$LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Get-Content "$sp\up0194.log" -Tail 8; exit 3 }
$check = & $py tools\publish_school_build.py check 2>&1
$check | Select-Object -Last 8
if (-not ($check -match 'download check: PASS')) { "CHECK FAILED"; exit 4 }
git status --short | Where-Object { $_ -match '^ M .*\.import$' } | ForEach-Object { git checkout -- $_.Substring(3) }
& $py tools\deploy_school.py --announce 3 --block-older --message "0.11.9.4 업데이트: 탐험 시작 때 소리·무기 미리 읽어 멈칫 줄임, 새 캐릭터 키 조정, 느린 인터넷·저사양 PC 대응"
"deploy exit=$LASTEXITCODE"
New-Item -ItemType Directory -Force D:\lsm26\old_release_01194 | Out-Null
Move-Item builds\release\Villagen_School_Setup.exe, builds\release\Villagen_School_Windows.zip D:\lsm26\old_release_01194\ -ErrorAction SilentlyContinue
"SHIPPED"
