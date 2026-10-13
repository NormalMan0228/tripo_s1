"""Puts the newest school build's download links at the top of README.md (the dev branch's front page).

Installers live on S3, not GitHub (see tools/publish_school_build.py; GitHub keeps code and history only). The
README links straight to the uploaded files, so one click on the dev page downloads Villagen_School_Setup.exe.
Run it after `publish_school_build.py upload`:
  python tools/update_download_links.py            # version from game/project.godot
  python tools/update_download_links.py 0.11.4
The block between the school-download markers is replaced; the first run inserts it under the title.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
HOST = json.loads((ROOT / "tools" / "download_host.json").read_text(encoding="utf-8"))
BASE = f"https://{HOST['bucket']}.s3.{HOST['region']}.amazonaws.com/{HOST['prefix'].strip('/')}"
START, END = "<!-- school-download:start -->", "<!-- school-download:end -->"


def version() -> str:
    text = (ROOT / "game" / "project.godot").read_text(encoding="utf-8")
    return re.search(r'config/version="([^"]+)"', text).group(1)


def sizes(ver: str) -> dict:
    """Read the public latest.json (so the README never points at a missing file)."""
    with urllib.request.urlopen(f"{BASE}/latest.json", timeout=30) as r:
        info = json.loads(r.read())
    if info["version"] != ver:
        raise SystemExit(f"S3 has {info['version']}, not {ver}; run publish_school_build.py upload first")
    return info


def block(ver: str, info: dict) -> str:
    url = lambda name: info["files"][name]["url"]
    gb = lambda name: f"{info['files'][name]['size'] / 1024 ** 3:.2f}GB"
    return "\n".join([
        START,
        f"## ⬇ 학교판 바로 설치 · {ver} ({info['date']})",
        "",
        f"### [▶ 설치 파일 받기 — Villagen_School_Setup.exe ({gb('Villagen_School_Setup.exe')})]({url('Villagen_School_Setup.exe')})",
        "",
        "받은 파일을 실행 → 설치 위치 선택 → 바탕화면·시작 메뉴에 **Villagen** 아이콘이 생깁니다. 이전 버전 위에 그대로 설치하면 됩니다.",
        "처음 실행할 때 Windows \"PC 보호\" 창이 뜨면 **추가 정보 → 실행**을 누르세요. 로그인 화면의 **학교 월드**에서 계정을 만듭니다.",
        "",
        f"- 설치 없이 쓰기: [Villagen_School_Windows.zip ({gb('Villagen_School_Windows.zip')})]({url('Villagen_School_Windows.zip')}) → 압축 풀고 `Villagen\\Villagen.exe`",
        f"- [내려받기 페이지]({info['page']}) · [체크섬]({url('SHA256SUMS_School.txt')}) · [로드맵](docs/roadmap/README.md)",
        "",
        "<sub>Install (Windows): download Villagen_School_Setup.exe above and run it. 安装：下载上面的 Villagen_School_Setup.exe 并运行。</sub>",
        END,
    ])


def main() -> None:
    ver = sys.argv[1] if len(sys.argv) > 1 else version()
    new = block(ver, sizes(ver))
    text = README.read_text(encoding="utf-8")
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: new, text, count=1, flags=re.S)
    else:
        title, _, rest = text.partition("\n")
        text = f"{title}\n\n{new}\n{rest}"
    README.write_text(text, encoding="utf-8")
    print("README download links ->", ver)


if __name__ == "__main__":
    main()
