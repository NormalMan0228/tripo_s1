$env:TRIPO_HEAVY_OWNER = '01'
Set-Location C:\lsm26\triphthonS1\.claude\worktrees\merge-vg
$py = '.tools\art-venv\Scripts\python.exe'
$g = '.tools\godot\Godot_v4.7.2-stable_win64_console.exe'
$sp = 'C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpad'
$sw = [Diagnostics.Stopwatch]::StartNew()
function T([string]$m) { "{0,5:N0}s {1}" -f $sw.Elapsed.TotalSeconds, $m }
function Gate { powershell -NoProfile -ExecutionPolicy Bypass -File D:\lsm26\locks\wait_heavy.ps1 -Owner 01 | Out-Null }
T ("head " + (git log --oneline -1) + " | " + (Select-String -Path game\project.godot -Pattern 'config/version').Line)
for ($i=1; $i -le 3; $i++) { Gate; & $g --headless --path game --import *> "$sp\b194_import.log"; T "import try $i exit=$LASTEXITCODE"; if ($LASTEXITCODE -eq 0) { break } }
git status --short | Where-Object { $_ -match '^ M .*\.import$' } | ForEach-Object { git checkout -- $_.Substring(3) }
Gate; & $py tools\bake_archipelago.py *> "$sp\b194_bake.log"; T ("island " + (Get-Content "$sp\b194_bake.log" -Tail 1))
Gate; & $py tools\bake_survival.py *> "$sp\b194_bake_s.log"; T ("survival " + (Get-Content "$sp\b194_bake_s.log" -Tail 1))
Gate; & $g --headless --path game --script res://tests/compile_all.gd *> "$sp\b194_compile.log"; T ("compile " + ((Select-String -Path "$sp\b194_compile.log" -Pattern 'COMPILE_DONE|COMPILE_FAIL' | ForEach-Object { $_.Line }) -join ' | '))
& $py tools\predeploy\check_client.py --assets-root (Get-Location).Path --summary *> "$sp\b194_predeploy.log"; T ("predeploy exit=$LASTEXITCODE"); Get-Content "$sp\b194_predeploy.log" -Tail 8 | ForEach-Object { "        $_" }
"changed after bakes:"; git status --short | Where-Object { $_ -notmatch '^\?\?' -and $_ -notmatch '\.import$' }
New-Item -ItemType Directory -Force builds\school | Out-Null
for ($i=1; $i -le 3; $i++) { Gate; & $g --headless --path game --export-release "Windows School" "../builds/school/Villagen.exe" *> "$sp\b194_export.log"; T "export try $i exit=$LASTEXITCODE"; if ($LASTEXITCODE -eq 0) { break } }
Get-ChildItem builds\school -File | ForEach-Object { T ("  {0} {1:N0} MB" -f $_.Name, ($_.Length/1MB)) }
& $py -c "import sys; sys.path.insert(0,'tools'); import game_patch as g; p=g.read_pck('builds/school/Villagen.pck'); raw=g.read_file('builds/school/Villagen.pck',p,'project.binary'); print('PCK_CHECK', raw[:4], len(raw), g.pack_version('builds/school/Villagen.pck',p))" *> "$sp\b194_pck.log"; T ("pck " + (Get-Content "$sp\b194_pck.log" -Raw).Trim())
if (-not (Select-String -Path "$sp\b194_pck.log" -Pattern "PCK_CHECK b'ECFG' \d+ 0\.11\.9\.4" -Quiet)) { T "PCK CHECK FAILED - stop"; exit 2 }
& $py tools\package_release.py --school --installer --game-only *> "$sp\b194_pkg.log"; T "package exit=$LASTEXITCODE"
Get-Content "$sp\b194_pkg.log" | Select-Object -Last 5 | ForEach-Object { "        $_" }
T "done"
T "all done"
