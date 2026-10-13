"""Writes the school build's install note at the top of README.md (the dev branch's front page).

The repository never links to installers or archives (GitHub restricted the account over a README
download link, 2026-10-12): the note gives the version and install steps only, and the download page's
address goes out through school announcements. Run it after `publish_school_build.py upload`:
  python tools/update_download_links.py            # version from game/project.godot
  python tools/update_download_links.py 0.11.4
The block between the school-download markers is replaced; the first run inserts it under the title.
"""
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START, END = "<!-- school-download:start -->", "<!-- school-download:end -->"
KST = datetime.timezone(datetime.timedelta(hours=9))


def version() -> str:
    text = (ROOT / "game" / "project.godot").read_text(encoding="utf-8")
    return re.search(r'config/version="([^"]+)"', text).group(1)


def block(ver: str, date: str) -> str:
    return "\n".join([
        START,
        f"## 학교판 설치 · {ver} ({date})",
        "",
        "설치 파일은 저장소에 두지 않습니다. 내려받기 주소는 **학교 공지(수업 게시판·단톡방)**로 안내합니다.",
        "",
        "받은 설치 파일을 실행 → 설치 위치 선택 → 바탕화면·시작 메뉴에 **Villagen** 아이콘이 생깁니다. 이전 버전 위에 그대로 설치하면 됩니다.",
        "처음 실행할 때 Windows \"PC 보호\" 창이 뜨면 **추가 정보 → 실행**을 누르세요. 로그인 화면의 **학교 월드**에서 계정을 만듭니다.",
        "버전별 바뀐 점은 [docs/releases/school_changes_KO.txt](docs/releases/school_changes_KO.txt), 계획은 [로드맵](docs/roadmap/README.md)에 있습니다.",
        END,
    ])


def main() -> None:
    ver = sys.argv[1] if len(sys.argv) > 1 else version()
    new = block(ver, datetime.datetime.now(KST).strftime("%Y-%m-%d"))
    text = README.read_text(encoding="utf-8")
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: new, text, count=1, flags=re.S)
    else:
        title, _, rest = text.partition("\n")
        text = f"{title}\n\n{new}\n{rest}"
    README.write_text(text, encoding="utf-8")
    print("README install note ->", ver)


if __name__ == "__main__":
    main()
