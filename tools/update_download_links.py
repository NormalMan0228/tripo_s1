"""Puts the newest school build's download links at the top of README.md (the dev branch's front page).

GitHub keeps installers in Releases, not in the branch, so the README links straight to the release
files: one click on the dev page downloads Villagen_School_Setup.exe. Run it after publishing a school
pre-release (tag v<version>-school, see tools/package_release.py --school):
  python tools/update_download_links.py            # version from game/project.godot
  python tools/update_download_links.py 0.11.4
The block between the school-download markers is replaced; the first run inserts it under the title.
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
REPO = "NormalMan0228/tripo_s1"
START, END = "<!-- school-download:start -->", "<!-- school-download:end -->"
KST = datetime.timezone(datetime.timedelta(hours=9))


def version() -> str:
    text = (ROOT / "game" / "project.godot").read_text(encoding="utf-8")
    return re.search(r'config/version="([^"]+)"', text).group(1)


def sizes(tag: str) -> dict:
    """Asset sizes from the published release (so the README never points at a missing file)."""
    out = subprocess.run(["gh", "release", "view", tag, "--repo", REPO, "--json", "assets,publishedAt"],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise SystemExit(f"release {tag} not found on GitHub; publish it first")
    data = json.loads(out.stdout)
    found = {a["name"]: a["size"] for a in data["assets"] if a.get("state", "uploaded") == "uploaded"}
    for name in ("Villagen_School_Setup.exe", "Villagen_School_Windows.zip"):
        if name not in found:
            raise SystemExit(f"{name} is not uploaded to {tag} yet")
    when = datetime.datetime.fromisoformat(data["publishedAt"].replace("Z", "+00:00")).astimezone(KST) if data.get("publishedAt") else datetime.datetime.now(KST)
    return {"files": found, "date": when.strftime("%Y-%m-%d")}


def block(ver: str, info: dict) -> str:
    tag = f"v{ver}-school"
    base = f"https://github.com/{REPO}/releases/download/{tag}"
    gb = lambda name: f"{info['files'][name] / 1024 ** 3:.2f}GB"
    return "\n".join([
        START,
        f"## ⬇ 학교판 바로 설치 · {ver} ({info['date']})",
        "",
        f"### [▶ 설치 파일 받기 — Villagen_School_Setup.exe ({gb('Villagen_School_Setup.exe')})]({base}/Villagen_School_Setup.exe)",
        "",
        "받은 파일을 실행 → 설치 위치 선택 → 바탕화면·시작 메뉴에 **Villagen** 아이콘이 생깁니다. 이전 버전 위에 그대로 설치하면 됩니다.",
        "처음 실행할 때 Windows \"PC 보호\" 창이 뜨면 **추가 정보 → 실행**을 누르세요. 로그인 화면의 **학교 월드**에서 계정을 만듭니다.",
        "",
        f"- 설치 없이 쓰기: [Villagen_School_Windows.zip ({gb('Villagen_School_Windows.zip')})]({base}/Villagen_School_Windows.zip) → 압축 풀고 `Villagen\\Villagen.exe`",
        f"- [이번 버전에서 바뀐 점](https://github.com/{REPO}/releases/tag/{tag}) · [체크섬]({base}/SHA256SUMS_School.txt) · [모든 버전](https://github.com/{REPO}/releases) · [로드맵](docs/roadmap/README.md)",
        "",
        "<sub>Install (Windows): download Villagen_School_Setup.exe above and run it. 安装：下载上面的 Villagen_School_Setup.exe 并运行。</sub>",
        END,
    ])


def main() -> None:
    ver = sys.argv[1] if len(sys.argv) > 1 else version()
    new = block(ver, sizes(f"v{ver}-school"))
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
