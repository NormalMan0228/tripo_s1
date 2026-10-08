"""Builds the GitHub release files (Villagen) from an exported player build.

    powershell -ExecutionPolicy Bypass -File tools/build_game.ps1   # exports builds/windows/
    .tools/art-venv/Scripts/python.exe tools/package_release.py

Writes builds/release/:
  Villagen_Windows.zip                  the game for players and judges: Villagen.exe +
                                         Villagen.pck (every map, NPC, interior, monster and
                                         UI asset inside), connects to the online world
  Villagen_<version>_DevAssets_Map.zip   game/maps/archipelago/assets (git-ignored)
  Villagen_<version>_DevAssets_Art.zip   the other git-ignored asset folders
  SHA256SUMS.txt
The DevAssets archives keep repository-relative paths: unzip them in the repository
root to run the game from source (Godot 4.7.2, game/project.godot). No keys,
invitation codes, server data or player databases are packaged.
"""
from __future__ import annotations

import hashlib
import sys
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "builds" / "windows"
SCHOOL_BUILD = ROOT / "builds" / "school"
OUT = ROOT / "builds" / "release"
MAP_ASSETS = ["game/maps/archipelago/assets"]
ART_ASSETS = ["game/assets/interior", "game/assets/monsters", "game/maps/survival/assets",
              "game/assets/portraits", "game/assets/npc"]
SECRET_WORDS = ("tripo_key", "api_key", "registration-code", "secrets/", ".env")
LIMIT = 2 * 1024 ** 3 - 16 * 1024 ** 2  # GitHub release files must stay under 2 GiB

README_KO = """Villagen — 빌리지 + 제너레이트 (Windows)
========================================

실행: 압축을 푼 폴더에서 Villagen.exe 를 실행합니다. (설치 불필요)
처음 실행 때 Windows가 "PC 보호" 창을 띄우면 [추가 정보] → [실행]을 누르세요.

온라인 월드
- 로그인 화면의 월드가 "온라인 월드"로 정해져 있습니다.
- [계정 만들기]에서 아이디와 비밀번호만 정하면 됩니다. (초대 코드 없음)
- 계정을 만들면 물건 제작을 바로 해 볼 수 있는 별씨가 들어 있습니다(체험판: 계정당 제작 3회).

물건 제작 (서버 → AI 설계 → Tripo 3D)
- 마을에서 C(제작)를 누르거나 집·공방에 들어가 [만들기]를 고릅니다.
- 만들고 싶은 물건을 문장으로 적으면 서버가 AI로 설계하고 Tripo로 3D 모델을 만듭니다.
- 견적을 확인한 뒤 [제작 확정]을 누르면 몇 분 뒤 가방에 들어옵니다. 원하는 곳에 놓고 색칠할 수 있습니다.
- 체험판에서는 직접 색칠하는 정적인 가구 한 덩어리를 만듭니다.

조작
- 이동 WASD · 달리기 Shift · 상호작용 E · 가방 I · 제작 C · 지도 Tab · 창고 B · 옷장 O
- HUD 접기/펼치기 U · 메뉴 Esc · 그림만 있는 버튼은 마우스를 올리면 이름이 보입니다.
- 목표 줄을 누르면 길 안내가 켜집니다. 설정(Esc → 설정)에서 그래픽·소리·키를 바꿀 수 있습니다.

문제가 생기면: 인터넷 연결과 Windows 방화벽을 확인하고, 다시 실행해 보세요.
"""

README_EN = """Villagen - village + generate (Windows)
=======================================

Run Villagen.exe from the unzipped folder (no installer). If Windows SmartScreen
appears, choose "More info" -> "Run anyway".

Online world: the login screen is set to the online world. Create an account with a
username and a password (no invitation code). New accounts start with enough stars
to try crafting (trial: 3 crafts per account, one static piece you paint yourself).

Crafting (server -> AI design -> Tripo 3D): press C in the village (or enter a house or
the workshop and choose Create), describe an object, check the estimate and confirm.
The model arrives in your bag a few minutes later; place and paint it in your room.

Controls: WASD move, Shift run, E interact, I bag, C craft, Tab map, B storage,
O wardrobe, U fold/unfold HUD, Esc menu. Hover icon-only buttons to see their names.
Click an objective line to start route guidance. Settings live under Esc -> Settings.
"""


def version() -> str:
    text = (ROOT / "game" / "project.godot").read_text(encoding="utf-8")
    return re.search(r'config/version="([^"]+)"', text).group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(path: Path) -> Path:
    if path.stat().st_size >= LIMIT:
        raise SystemExit(f"{path.name} is {path.stat().st_size / 1024 ** 3:.2f} GiB, over GitHub's 2 GiB file limit")
    return path


def game_zip(tag: str) -> Path:
    school = "--school" in sys.argv
    build = SCHOOL_BUILD if school else BUILD
    exe, pck = build / "Villagen.exe", build / "Villagen.pck"
    for item in (exe, pck):
        if not item.is_file(): raise SystemExit(f"missing {item}; export the 'Windows {'School' if school else 'Desktop'}' preset first")
    if school and 'SCHOOL_SERVER := ""' in (ROOT / "game" / "scripts" / "main.gd").read_text(encoding="utf-8"):
        raise SystemExit("set SCHOOL_SERVER in game/scripts/main.gd to the school server address first")
    # A fixed name, so .../releases/latest/download/Villagen_Windows.zip always points at the newest game.
    # School builds (--school) ship as pre-releases under their own name and never replace it.
    target = OUT / ("Villagen_School_Windows.zip" if school else "Villagen_Windows.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(exe, "Villagen/Villagen.exe")
        archive.write(pck, "Villagen/Villagen.pck")
        readme = README_KO
        if school:
            # School builds play on the school server with its own rules (docs/SCHOOL_SERVER_KO.txt).
            for trial, rule in (('"온라인 월드"', '"학교 월드"'), ("(체험판: 계정당 제작 3회)", "(학교 서버: 계정당 하루 3회)"),
                                ("- 체험판에서는 직접 색칠하는 정적인 가구 한 덩어리를 만듭니다.",
                                 "- 학교 서버에서는 Tripo가 색까지 입혀 만들고, 참고 사진과 움직이는 2~3부품 가구도 됩니다(1회 최대 35크레딧).")):
                readme = readme.replace(trial, rule)
        archive.writestr("Villagen/README_KO.txt", readme.replace("\n", "\r\n").encode("utf-8-sig"))
        archive.writestr("Villagen/README_EN.txt", README_EN.replace("\n", "\r\n"))
        for licence in sorted((ROOT / "docs" / "licenses").glob("*")):
            archive.write(licence, f"Villagen/licenses/{licence.name}")
        archive.write(ROOT / "game" / "assets" / "fonts" / "LICENSES.md", "Villagen/licenses/Fonts-LICENSES.md")
    return check(target)


def assets_zip(tag: str, name: str, folders: list[str]) -> Path:
    target = OUT / f"Villagen_{tag}_DevAssets_{name}.zip"
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for folder in folders:
            base = ROOT / folder
            if not base.exists(): continue
            for item in sorted(base.rglob("*")):
                if not item.is_file(): continue
                relative = item.relative_to(ROOT).as_posix()
                if any(word in relative.lower() for word in SECRET_WORDS):
                    raise SystemExit(f"refusing to package a secret-looking path: {relative}")
                archive.write(item, relative)
                count += 1
    print(f"{target.name}: {count} files")
    return check(target)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "v" + version()
    if "--installer" in sys.argv:
        # Windows installer (Inno Setup, tools/installer/villagen.iss): pick a folder, desktop and Start
        # menu shortcuts, uninstaller. Writes Villagen_School_Setup.exe or Villagen_Setup.exe.
        import subprocess
        edition = "school" if "--school" in sys.argv else "public"
        compiler = ROOT / ".tools" / "innosetup" / "ISCC.exe"
        if not compiler.is_file(): raise SystemExit("Inno Setup missing: .tools/innosetup/ISCC.exe")
        subprocess.run([str(compiler), "/Q", f"/DEdition={edition}", f"/DAppVer={version()}",
                        str(ROOT / "tools" / "installer" / "villagen.iss")], check=True)
        setup = OUT / ("Villagen_School_Setup.exe" if edition == "school" else "Villagen_Setup.exe")
        print(f"{setup.name}  {setup.stat().st_size / 1024 ** 2:.0f} MB")
        if "--game-only" not in sys.argv: return
    # --game-only: just the player ZIP (the DevAssets archives change rarely; reuse the last ones).
    files = [game_zip(tag)] if "--game-only" in sys.argv else [game_zip(tag), assets_zip(tag, "Map", MAP_ASSETS), assets_zip(tag, "Art", ART_ASSETS)]
    sums = OUT / ("SHA256SUMS_School.txt" if "--school" in sys.argv else "SHA256SUMS.txt")
    sums.write_text("".join(f"{sha256(f)}  {f.name}\n" for f in files), encoding="utf-8")
    for item in files + [sums]:
        print(f"{item.name}  {item.stat().st_size / 1024 ** 2:.0f} MB")


if __name__ == "__main__":
    main()
