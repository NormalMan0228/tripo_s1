"""Build the local Korean handoff, linked reference pages and an offline bundle.

Run with .tools/art-venv/Scripts/python.exe; requires Markdown and Pillow.
Only allowlisted documents/media are exported. No user DB or credential files.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, unquote
from urllib.request import urlopen
import csv
import hashlib
import json
import re
import shutil
import subprocess
import zipfile

import markdown
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/TRIPOTHON_MASTER_HANDOFF_20261003.md"
REVIEW = ROOT / "artifacts/production-lab-20261003/review"
DEST = REVIEW / "master-handoff"
RECORDS = ROOT / "artifacts/master-handoff-20261003"
DOC_MEDIA = ROOT / "docs/media/master-handoff-20261003"
LOCAL_URL = "http://127.0.0.1:8842/master-handoff/index.html"

SECTIONS = [
    ("summary", "01 요약"), ("direction", "02 방향·범위"),
    ("status", "03 실제 완료 상태"), ("architecture", "04 시스템 연결"),
    ("security", "05 서버·보안"), ("pipelines", "06 생성 파이프라인"),
    ("character", "07 캐릭터 세부 제작"), ("animation", "08 애니메이션"),
    ("environment", "09 맵·환경·실내"), ("tools", "10 도구 상태"),
    ("costs", "11 모델·비용"), ("economics", "12 저비용·상업 이용"),
    ("roadmap", "13 기존 8단계 계획"), ("next", "14 추천 처리 순서"),
    ("schedule", "15 일정·협업"), ("watch", "16 영상·공식 문서"),
    ("library", "17 자료·결과물 위치"), ("run", "18 실행·검증"),
    ("pending", "19 남은 판단"),
]
DOCUMENTS = [
    "README.md", "docs/BASELINE_091.md", "docs/CONTROLLER_092.md",
    "docs/ART_TOOLS_AND_VILLAGE_20261003.md",
    "docs/CHARACTER_ANIMATION_WORKFLOW_20261003.md",
    "docs/CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003.md",
    "docs/CHARACTER_PART_REFERENCES_20261003.md",
    "docs/EXPLORER_PARTS_20261003.md",
    "docs/AI_CHARACTER_DETAIL_REFERENCES_20261003.md",
    "docs/SERVER_STATUS_20261003.md", "docs/SECURITY.md",
    "docs/DEPLOYMENT.md", "ops/README.md", "docs/VILLAGE.md",
    "docs/ASSETS.md", "docs/TEST_REPORT.md", "docs/initial-handoff-notes.md",
]
CSS = r"""
:root{--bg:#f4f5f1;--paper:#fff;--ink:#172b31;--muted:#536a70;--line:#dce3df;--accent:#146e63;--pale:#e9f2eb;--gold:#b5782b}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Malgun Gothic',system-ui,sans-serif;line-height:1.85;font-size:15px}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}a:hover{color:#9a6121}
.sidebar{position:fixed;inset:0 auto 0 0;width:265px;padding:28px 22px;background:#173c3e;color:#edf5ef;overflow-y:auto}
.brand{font-size:12px;letter-spacing:2px;color:#b9d6c8}.sidebar h2{font-size:22px;margin:6px 0 12px;line-height:1.5}.sidebar small{display:block;color:#bdd3cd;font-size:12px}
.sidebar nav{margin-top:24px;display:grid;gap:4px}.sidebar nav a{display:block;color:#d8e7e0;text-decoration:none;padding:7px 11px;border-radius:7px;font-size:13px;line-height:1.5}
.sidebar nav a.active,.sidebar nav a:hover{background:#2c5551;color:#fff}.sidebar .foot{margin-top:28px;color:#bdd3cd;font-size:11px}
.shell{margin-left:265px;padding:36px 4vw 70px;max-width:1570px}.masthead{display:flex;justify-content:space-between;align-items:center;gap:20px;border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:30px;font-size:12px;color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap}.actions a,.actions button{border:1px solid #bbcfbf;background:#fff;border-radius:6px;padding:7px 12px;font:inherit;color:var(--accent);cursor:pointer;text-decoration:none}
article{max-width:1080px;margin:auto;background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:44px 48px;box-shadow:0 8px 32px #173c3e07}
h1{font-size:34px;line-height:1.4;letter-spacing:-1px;margin:0 0 15px}h2{font-size:25px;line-height:1.5;margin:62px 0 20px;padding-bottom:12px;border-bottom:2px solid var(--line);letter-spacing:-.6px}h3{font-size:19px;line-height:1.55;margin:30px 0 14px}
p{margin:14px 0}strong{font-weight:750}ul,ol{padding-left:24px}li{padding-left:3px;margin:8px 0}
#summary+h2{margin-top:38px}.summary-intro{font-size:17px;color:#254b49}.summary-list{background:var(--pale);border-left:4px solid var(--accent);padding:16px 24px 16px 38px;border-radius:0 10px 10px 0}
.table-wrap{overflow:auto;margin:22px 0;border:1px solid var(--line);border-radius:9px}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.8;min-width:580px}th,td{text-align:left;vertical-align:top;padding:13px 15px;border-bottom:1px solid var(--line)}th{background:#edf3ef;font-weight:700;white-space:nowrap}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f9fbf8}td:first-child{min-width:120px}td code{overflow-wrap:anywhere}
code{font-family:Consolas,monospace;font-size:12px;background:#f0f3ef;border-radius:4px;padding:2px 4px;overflow-wrap:anywhere}pre{background:#17383a;color:#edf7f0;padding:20px;border-radius:9px;overflow:auto;line-height:1.75}pre code{background:none;color:inherit;padding:0}
img{max-width:100%;height:auto;display:block;border-radius:9px}video{width:100%;display:block;max-height:600px;background:#142c30;border-radius:9px}figure{margin:0}figcaption{font-size:12px;color:var(--muted);margin-top:9px}
.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:26px 0}.gallery img{aspect-ratio:16/10;object-fit:cover}.media-card{padding:16px;background:#f3f6f1;border:1px solid var(--line);border-radius:12px}.media-card h3{margin:0 0 12px;font-size:17px}.media-card p{font-size:13px}.media-card .small{font-size:12px;color:var(--muted)}
.flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:24px 0}.flow div{background:var(--pale);border-top:3px solid var(--accent);padding:14px 11px;border-radius:6px;font-size:12px}.flow b{display:block;margin:5px 0;font-size:14px}.flow span{color:var(--muted);font-size:11px}
details{border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin:15px 0;background:#fafbf8}summary{font-weight:700;color:var(--accent);cursor:pointer}.notice{padding:14px 18px;border-left:4px solid var(--gold);background:#fff6e6;font-size:13px}.caption{font-size:12px;color:var(--muted)}.chapter-return{display:block;text-align:right;font-size:12px;margin-top:20px}.endnote{margin-top:36px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media(max-width:1050px){.sidebar{width:225px;padding:22px 15px}.shell{margin-left:225px;padding:26px 22px}article{padding:32px 26px}h1{font-size:29px}.flow{grid-template-columns:1fr 1fr}table{min-width:0;font-size:12px}th,td{padding:11px 9px}th{white-space:normal}td:first-child{min-width:0}}
@media(max-width:760px){.sidebar{position:static;width:auto;padding:20px}.sidebar nav{display:flex;overflow:auto;gap:8px;margin-top:12px;padding-bottom:6px}.sidebar nav a{white-space:nowrap}.sidebar .foot,.sidebar small{display:none}.shell{margin:0;padding:16px 10px}article{padding:26px 18px;border-radius:10px}.masthead{flex-direction:column;align-items:flex-start;margin-bottom:16px}.gallery{grid-template-columns:1fr}h1{font-size:26px}h2{font-size:22px}.flow{grid-template-columns:1fr 1fr}}
@media print{body{background:#fff;font-size:10pt}.sidebar,.masthead,.chapter-return{display:none}.shell{margin:0;padding:0;max-width:none}article{padding:0;border:0;box-shadow:none;max-width:none}h1{font-size:23pt}h2{font-size:17pt;page-break-after:avoid;margin-top:28px}h3{page-break-after:avoid}.table-wrap{overflow:visible}table{min-width:0;font-size:9pt}td,th{padding:7px;overflow-wrap:anywhere}tr,figure{break-inside:avoid}video{display:none}.gallery{display:block}.gallery figure{width:47%;display:inline-block;margin:1%}a{color:#173c3e}details>*{display:block}.flow{grid-template-columns:repeat(5,1fr)}}
"""


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def relname(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def doc_slug(rel: str) -> str:
    return rel.replace("/", "--").removesuffix(".md")


def clean_cell(text) -> str:
    return str(text).replace("|", " / ").replace("\n", " ")


def snapshot() -> dict:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    states = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines()
    origin = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
    url = urlsplit(origin)
    safe_origin = urlunsplit((url.scheme, url.hostname or "", url.path, "", "")) if url.scheme else origin
    health = {"endpoint": "https://34-28-65-113.sslip.io/health"}
    try:
        with urlopen(health["endpoint"], timeout=15) as response:
            fields = json.load(response)
        health.update({k: fields.get(k) for k in ("ok", "mode", "protocol", "studio_tripo_enabled")})
        health["read_only_check"] = "success"
    except Exception as error:
        health.update({"read_only_check": "failed", "error_type": type(error).__name__})
    return {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Documentation snapshot; no fresh game test, account mutation or paid generation",
        "git": {"branch": branch, "commit": commit, "origin": safe_origin,
                "changed_or_untracked_entries_before_build": len(states)},
        "health": health,
        "current_game_project_exists": (ROOT / "game/project.godot").is_file(),
        "baseline092_exists": (ROOT / "builds/Tripothon_Baseline_092").is_dir(),
        "files": [{"path": name, "bytes": (ROOT / name).stat().st_size,
                   "sha256": digest(ROOT / name)} for name in DOCUMENTS],
    }


def copy_media():
    images = [
        ("artifacts/detail-map-20261003/playtest/village-overview.png", "village-overview.jpg"),
        ("artifacts/detail-map-20261003/playtest/closeup/closeup-npc.png", "closeup-npc.jpg"),
        ("artifacts/detail-map-20261003/playtest/cottage-interior.png", "cottage-interior.jpg"),
        ("artifacts/detail-map-20261003/character/hand-godot.png", "hand-godot.jpg"),
        ("art/references/explorer_b_v5/front.png", "explorer-b-reference.jpg"),
        ("artifacts/video-motion-20261003/source-result-contact.jpg", "video-comparison.jpg"),
    ]
    for rel, name in images:
        source = ROOT / rel
        with Image.open(source) as im:
            im = im.convert("RGB")
            im.thumbnail((1280, 1000))
            im.save(DEST / "assets" / name, "JPEG", quality=89, optimize=True)
            shutil.copy2(DEST / "assets" / name, DOC_MEDIA / name)
    videos = [
        ("artifacts/detail-map-20261003/playtest/closeup/village-closeup-play.mp4", "village-closeup-play.mp4"),
        ("artifacts/detail-map-20261003/character/hand-godot-motion.mp4", "hand-godot-motion.mp4"),
        ("artifacts/video-motion-20261003/comparison-game.mp4", "video-animation-comparison.mp4"),
    ]
    for rel, name in videos:
        shutil.copy2(ROOT / rel, DEST / "videos" / name)


def resource_catalog() -> str:
    data = json.loads((ROOT / "docs/character-detail-references.json").read_text(encoding="utf-8-sig"))
    paragraphs = []
    for i, r in enumerate(data["resources"], 1):
        block = [f"#### {i:02d}. {clean_cell(r['channel'])} · {clean_cell(r['title'])}",
                 f"[{r['title']}]({r['url']}) · **{r['priority']}** · {r['access']}",
                 f"**볼 부분:** {r['range']}",
                 f"**우리 작업에 쓰는 이유:** {r['fit']}",
                 f"**남는 결과·한계:** {r['output']} {r['limit']}",
                 f"**확인 수준:** {r['verified']}"]
        if r.get("local"):
            local = r["local"].replace("character__b2_claude_in_blender.txt", "character__b1_claude_in_blender.txt")
            block.append(f"보유 자료: `{local}`. 강의 원문은 팀의 보유 자료에서 열며 공유 묶음에는 넣지 않습니다.")
        if r.get("extra"):
            block.append("함께 볼 문서: " + " · ".join(f"[{item['label']}]({item['url']})" for item in r["extra"]))
        paragraphs.append("\n\n".join(block))
    return "\n\n".join(paragraphs)


def deliverables() -> str:
    return """| 결과 | 문서·영상 연결 | 원본·검증 위치 |
| --- | --- | --- |
| 근접 플레이 영상 | [이 문서의 영상](#closeup-video), [기존 근접 영상 페이지](http://127.0.0.1:8842/closeup-play.html) | `artifacts/detail-map-20261003/playtest/closeup/` |
| 도구·새 마을 보고서 | [기존 아트 실험 보고서](http://127.0.0.1:8842/art-slice.html) | `artifacts/detail-map-20261003/`, 편집 소스와 Godot labs |
| 손 리그 동작 | [이 문서의 손 영상](#hand-video) | `artifacts/detail-map-20261003/character/hand-godot-motion.mp4` |
| 생산 워크플로우·영상 3종·비용 | [기존 생산 보고서](http://127.0.0.1:8842/) | `artifacts/production-lab-20261003/`, `experiment.json` |
| 영상 각각에서 만든 동작 | [이 문서의 비교 영상](#motion-video), [기존 원본/결과 동시 비교](http://127.0.0.1:8842/video-animations.html) | `artifacts/video-motion-20261003/`, 6클립·재임포트·Godot 검사 |
| 세부 캐릭터 자료집 | [보관한 세부 자료집](AI_CHARACTER_DETAIL_REFERENCES_20261003.md), [기존 웹 자료집](http://127.0.0.1:8842/character-detail-references.html) | `docs/character-detail-references.json` 포함 17자료 |
| LLM 모델/effort 비교 | [요약 CSV](../artifacts/model-comparison/summary.csv) | `artifacts/model-comparison/summary.json`, 원래 index.html |
| 구조화 생성 별도 비교 | [요약 CSV](../artifacts/model-benchmark-structured-publication/summary.csv) | `artifacts/model-benchmark-structured-publication/` |
| 이미지 가구 실험 | [검증 기록](TEST_REPORT.md) | `artifacts/picture-furniture-20261002/` 및 공방 검사 |
| 기존 오프라인 보고서 묶음 | 보고서 서버가 필요한 기존 웹 링크와 별도로 ZIP 보관 | review의 `Tripothon_Report_With_Videos_20261003.zip`, `Tripothon_Production_Report_20261003.pdf` |
| 아트·영상 원본 묶음 | 게임 에셋·소스가 필요할 때 별도 사용 | `artifacts/detail-map-20261003/Tripothon_Art_Slice_20261003.zip`, `artifacts/video-motion-20261003/Tripothon_Video_Motions_20261003.zip` |

기존 아트 ZIP은 최근 근접 카메라 촬영보다 먼저 생성했습니다. 최신 근접 영상은 이 통합 문서 묶음에 별도 포함합니다. 기존 웹 보고서 링크는 `127.0.0.1:8842` 보고서 서버가 켜져 있어야 열립니다. 이 문서의 요약·목차·선별 문서·영상은 오프라인 폴더에서도 볼 수 있습니다."""


def add_generated_content():
    text = SOURCE.read_text(encoding="utf-8")
    start, end = "<!-- RESOURCE_CATALOG_START -->", "<!-- RESOURCE_CATALOG_END -->"
    resource = start + "\n\n" + resource_catalog() + "\n\n" + end
    if "<!-- RESOURCE_CATALOG -->" in text:
        text = text.replace("<!-- RESOURCE_CATALOG -->", resource)
    else:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: resource, text, flags=re.S)
    lib_start, lib_end = "<!-- DELIVERABLE_LIBRARY_START -->", "<!-- DELIVERABLE_LIBRARY_END -->"
    library = lib_start + "\n\n" + deliverables() + "\n\n" + lib_end
    if "<!-- DELIVERABLE_LIBRARY -->" in text:
        text = text.replace("<!-- DELIVERABLE_LIBRARY -->", library)
    else:
        text = re.sub(re.escape(lib_start) + r".*?" + re.escape(lib_end), lambda _: library, text, flags=re.S)
    picture_start, picture_end = '<!-- MASTER_PICTURES_START -->', '<!-- MASTER_PICTURES_END -->'
    pictures = picture_start + '\n\n![새 마을 대표 구역](media/master-handoff-20261003/village-overview.jpg)\n\n![독립 손 리그](media/master-handoff-20261003/hand-godot.jpg)\n\n' + picture_end
    if picture_start in text:
        text = re.sub(re.escape(picture_start) + r'.*?' + re.escape(picture_end), lambda _: pictures, text, flags=re.S)
    else:
        text = text.replace('<!-- MASTER_PICTURES -->', '')
        text = text.replace('![새 마을 대표 구역](media/master-handoff-20261003/village-overview.jpg)', '')
        text = text.replace('![독립 손 리그](media/master-handoff-20261003/hand-godot.jpg)', '')
        text = text.replace('<a id="architecture"></a>', pictures + '\n\n<a id="architecture"></a>')
    for anchor, title, description in [
        ('closeup-video', '근접 플레이 · 실제 이동과 건물 출입', '20.87초 · 1728×1080 · 30fps · 별도 마을 실험실.'),
        ('hand-video', '독립 손의 쥐기 동작', 'Blender에서 작성한 독립 손 동작의 Godot 검토.'),
        ('motion-video', '영상 3종에서 만든 몸 동작 비교', '각 원본에서 전이한 5초 시퀀스. 손가락·얼굴 캡처는 포함하지 않음.'),
    ]:
        marker = 'MASTER_' + anchor.upper().replace('-', '_')
        section = f'<a id="{anchor}"></a>\n\n<!-- {marker}_START -->\n\n### {title}\n\n{description}\n\n[HTML에서 재생]({LOCAL_URL}#{anchor})\n\n<!-- {marker}_END -->\n\n'
        if f'<a id="{anchor}"></a>' in text:
            pattern = re.escape(f'<a id="{anchor}"></a>') + r'.*?(?=<a id="(?:closeup-video|hand-video|motion-video|environment)"></a>)'
            text = re.sub(pattern, lambda _: section, text, count=1, flags=re.S)
        else:
            text = text.replace('<a id="environment"></a>', section + '<a id="environment"></a>')
    SOURCE.write_text(text, encoding="utf-8")
    return text


def body_from_md(text: str) -> str:
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    return body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")


def page(title: str, body: str, *, main=False) -> str:
    nav = "".join(f'<a href="#{id_}">{escape(label)}</a>' for id_, label in SECTIONS) if main else '<a href="../index.html">통합 문서로 돌아가기</a>'
    sidebar = f'<aside class="sidebar"><div class="brand">TRIPOTHON / TEAM NOTES</div><h2>{"제작 현황과<br>다음 작업" if main else "보관 참고 문서"}</h2><small>2026.10.03 · 한국 시간<br>{"목차를 눌러 상세 내용으로 이동" if main else "원래 문서의 기록 시점·버전을 확인하세요"}</small><nav>{nav}</nav><div class="foot">검증된 기준본 0.9.2<br>새 아트는 별도 실험실<br>기록과 제안을 구분합니다.</div></aside>'
    actions = '<a href="Tripothon_Master_Handoff_20261003.md" download>Markdown 원본</a><a href="../Tripothon_Master_Handoff_20261003.zip" download>오프라인 묶음</a><button onclick="window.print()">인쇄 / PDF 저장</button>' if main else '<a href="../index.html">통합 목차</a>'
    js = """
const ids=Array.from(document.querySelectorAll('.sidebar nav a[href^="#"]'));
const nodes=ids.map(a=>document.getElementById(a.hash.slice(1))).filter(Boolean);
const highlight=()=>{let current=nodes[0];for(const n of nodes)if(n.getBoundingClientRect().top<170)current=n;ids.forEach(a=>a.classList.toggle('active',a.hash==='#'+current.id));};
window.addEventListener('scroll',highlight,{passive:true});highlight();
document.querySelectorAll('a[href^="https://"]').forEach(a=>{a.target='_blank';a.rel='noopener noreferrer';});
""" if main else ""
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{CSS}</style></head><body>{sidebar}<div class="shell"><header class="masthead"><span>제작·검증·자료·계획을 연결한 팀 내부 인계 문서</span><div class="actions">{actions}</div></header><article>{body}<footer class="endnote">로컬에 보관한 2026-10-03 기록입니다. 최신 계정 잔액·가격·제출·운영 상태는 해당 근거에서 다시 확인합니다.</footer></article></div><script>{js}</script></body></html>'


class LinkRewriter(HTMLParser):
    def __init__(self, source: Path, current_page: Path, doc_map: dict):
        super().__init__(convert_charrefs=False)
        self.source, self.current_page, self.doc_map = source, current_page, doc_map
        self.out = []

    def handle_starttag(self, tag, attrs):
        fixed = []
        for key, value in attrs:
            if key in ("href", "src") and value and not value.startswith(("#", "http://", "https://", "data:", "mailto:")):
                split = urlsplit(value)
                candidate = (self.source.parent / unquote(split.path)).resolve()
                if candidate.is_file() and candidate.is_relative_to(ROOT):
                    if candidate in self.doc_map:
                        target = self.doc_map[candidate]
                    elif candidate.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        target = DEST / "assets" / (hashlib.sha256(str(candidate).encode()).hexdigest()[:10] + candidate.name)
                        if not target.exists():
                            shutil.copy2(candidate, target)
                    elif candidate.suffix.lower() == ".csv":
                        target = DEST / "data" / (candidate.parent.name + "-" + candidate.name)
                        shutil.copy2(candidate, target)
                    else:
                        # Retain repo-relative location as text for non-document artifacts.
                        # No broad recursive export of assets, paid transcripts or user data.
                        target = None
                    if target:
                        import os
                        value = Path(os.path.relpath(target, self.current_page.parent)).as_posix()
                        if split.fragment:
                            value += "#" + split.fragment
                    else:
                        value = "#artifact-locations" if self.current_page.name == "index.html" else "../index.html#library"
                elif tag == "img":
                    # Old reference media may not exist in this checkout. Leave an explicit note.
                    self.out.append('<span class="caption">이미지 원본 위치: ' + escape(value) + '</span>')
                    return
                elif candidate.suffix == ".md" or split.scheme.lower() in ("c", "file"):
                    value = "../index.html#library" if self.current_page.parent.name == "references" else "#library"
            fixed.append(key if value is None else f'{key}="{escape(value, quote=True)}"')
        self.out.append("<" + tag + (" " + " ".join(fixed) if fixed else "") + ">")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag): self.out.append(f"</{tag}>")
    def handle_data(self, data): self.out.append(data)
    def handle_entityref(self, name): self.out.append(f"&{name};")
    def handle_charref(self, name): self.out.append(f"&#{name};")
    def handle_comment(self, data): self.out.append(f"<!--{data}-->")


def rewrite(body: str, source: Path, target: Path, doc_map: dict) -> str:
    parser = LinkRewriter(source, target, doc_map)
    parser.feed(body)
    return "".join(parser.out)


def build_pages(text: str):
    mapping = {ROOT / rel: DEST / "references" / (doc_slug(rel) + ".html") for rel in DOCUMENTS}
    mapping[SOURCE] = DEST / "index.html"
    for rel in DOCUMENTS:
        source = ROOT / rel
        dest = mapping[source]
        original = source.read_text(encoding="utf-8-sig")
        shutil.copy2(source, dest.with_suffix(".md"))
        title = next((x.removeprefix("# ") for x in original.splitlines() if x.startswith("# ")), source.name)
        body = rewrite(body_from_md(original), source, dest, mapping)
        body = '<p class="notice">선별 보관한 기존 문서입니다. 문서에 적힌 버전·날짜의 기록이며, 현재 상태는 통합 문서의 현황표를 먼저 확인하세요.</p>' + body
        dest.write_text(page(title, body), encoding="utf-8")
    html_text = re.sub(r'<!-- MASTER_PICTURES_START -->.*?<!-- MASTER_PICTURES_END -->', '<!-- MASTER_PICTURES -->', text, flags=re.S)
    for anchor in ('closeup-video', 'hand-video', 'motion-video'):
        marker = 'MASTER_' + anchor.upper().replace('-', '_')
        html_text = re.sub(r'<!-- ' + marker + r'_START -->.*?<!-- ' + marker + r'_END -->', '<!-- ' + marker + ' -->', html_text, flags=re.S)
    body = rewrite(body_from_md(html_text), SOURCE, DEST / "index.html", mapping)
    body = re.sub(r'(?:<p>)?<a id="contents"></a>(?:</p>)?\s*<h2[^>]*>목차</h2>(.*?)(?=(?:<p>)?<a id="direction")', r'<details class="full-toc"><summary id="contents">전체 목차 펼치기 · 왼쪽 목차에서도 바로 이동</summary>\1</details>', body, flags=re.S)
    body = re.sub(r'(<h2[^>]*>01\. 상단 요약</h2>\s*)<p>', r'\1<p class="summary-intro">', body)
    summary_start = body.find('<a id="summary"')
    first_list = body.find('<ul>', summary_start)
    body = body[:first_list] + body[first_list:].replace('<ul>', '<ul class="summary-list">', 1)
    gallery = '<div class="gallery">' + "".join(
        f'<figure><img loading="lazy" src="assets/{name}" alt="{escape(caption)}"><figcaption>{escape(caption)}</figcaption></figure>' for name, caption in [
            ("village-overview.jpg", "새 마을 대표 구역 · 별도 아트 실험실"),
            ("closeup-npc.jpg", "해루 상호작용 · 실제 Godot 근접 촬영"),
            ("cottage-interior.jpg", "실내 출입·귀환 시험 · 서버 배치 통합은 후속"),
            ("hand-godot.jpg", "독립 손 리그 검토 · 주인공 몸체 결합 전"),
        ]) + '</div>'
    body = body.replace('<!-- MASTER_PICTURES -->', gallery)
    cards = [
        ("closeup-video", "근접 플레이 · 실제 이동과 건물 출입", "village-closeup-play.mp4", "closeup-npc.jpg", "20.87초 · 1728×1080 · 30fps · 별도 마을 실험실. 캐릭터 모터·충돌·NPC 대화·건물 출입을 사용했습니다."),
        ("hand-video", "독립 손의 쥐기 동작", "hand-godot-motion.mp4", "hand-godot.jpg", "약 5초 Godot 재생 검토. Blender 작성 동작이며 얼굴·몸체 맞춤까지 완료한 결과는 아닙니다."),
        ("motion-video", "영상 3종에서 만든 몸 동작 비교", "video-animation-comparison.mp4", "video-comparison.jpg", "각 원본 영상의 동작 추적·리타기팅 결과. 5초 시퀀스 비교이며 손가락·얼굴 캡처는 포함하지 않습니다."),
    ]
    for anchor, title, file, poster, caption in cards:
        marker = '<!-- MASTER_' + anchor.upper().replace('-', '_') + ' -->'
        body = body.replace(marker, f'<section class="media-card"><h3>{title}</h3><video controls playsinline preload="metadata" poster="assets/{poster}" src="videos/{file}"></video><p>{caption}</p></section>')
    flow = '<div class="flow">' + ''.join(f'<div><span>{i:02d}</span><b>{label}</b>{description}</div>' for i, (label, description) in enumerate([
        ('디자인·척도','컨셉·체형·접합 규격'), ('메시·재질','부품·UV·베이크·색'),
        ('리그·변형','뼈·웨이트·표정'), ('동작·접촉','루프·속도·전환'),
        ('게임·저장','충돌·UI·서버·검수')], 1)) + '</div>'
    body = body.replace('<h3>고품질 캐릭터의 추천 제작 순서</h3>', '<h3>고품질 캐릭터의 추천 제작 순서</h3>' + flow)
    body = body.replace('<h3>소스·편집 원본·실행 에셋</h3>', '<a id="artifact-locations"></a><h3>소스·편집 원본·실행 에셋</h3>')
    body += '<a class="chapter-return" href="#summary">↑ 요약으로 돌아가기</a>'
    (DEST / "index.html").write_text(page("Tripothon 제작 현황·자료·실행 계획", body, main=True), encoding="utf-8")
    # Markdown copy remains useful without the HTML renderer and keeps repository paths.
    packaged_md = text.replace('(media/master-handoff-20261003/', '(assets/')
    for rel in DOCUMENTS:
        original = ROOT / rel
        import os
        source_href = Path(os.path.relpath(original, SOURCE.parent)).as_posix()
        packaged_md = packaged_md.replace('](' + source_href + ')', '](references/' + doc_slug(rel) + '.md)')
    for cohort in ('model-comparison', 'model-benchmark-structured-publication'):
        packaged_md = packaged_md.replace(f'](../artifacts/{cohort}/summary.csv)', f'](data/{cohort}-summary.csv)')
    (DEST / "Tripothon_Master_Handoff_20261003.md").write_text(packaged_md, encoding="utf-8")


def copy_data_and_validate():
    records = [
        "artifacts/detail-map-20261003/budget.json",
        "artifacts/detail-map-20261003/map-manifest.json",
        "artifacts/detail-map-20261003/installed-tools.json",
        "artifacts/detail-map-20261003/playtest/closeup/closeup-audit.json",
        "artifacts/production-lab-20261003/experiment.json",
        "artifacts/video-motion-20261003/godot-acceptance.json",
        "artifacts/video-motion-20261003/reimport-audit.json",
        "docs/character-detail-references.json",
    ]
    for rel in records:
        shutil.copy2(ROOT / rel, DEST / "data" / Path(rel).name)
    roadmap = Path("C:/Users/dd/.codex/visualizations/2026/09/30/01a0f276-190b-72b3-bbcb-8277fd264084/game-system-roadmap.json")
    if roadmap.exists():
        shutil.copy2(roadmap, DEST / "data/game-system-roadmap.json")
    unresolved = []
    anchors_checked = 0
    class Links(HTMLParser):
        def __init__(self): super().__init__(); self.ids=set(); self.links=[]
        def handle_starttag(self, tag, attrs):
            attrs=dict(attrs)
            if attrs.get('id'): self.ids.add(attrs['id'])
            for k in ('href','src'):
                if attrs.get(k): self.links.append((tag,attrs[k]))
    parsers = {}
    for p in DEST.rglob('*.html'):
        parser=Links(); parser.feed(p.read_text(encoding='utf-8')); parsers[p]=parser
    for p, parser in parsers.items():
        for tag, url in parser.links:
            if url.startswith(('http://','https://','data:','mailto:')): continue
            split=urlsplit(url)
            target=(p.parent/unquote(split.path)).resolve() if split.path else p
            if target.suffix=='.zip': continue  # Bundle created after validation.
            if not target.is_file(): unresolved.append({'page':p.name,'url':url,'reason':'missing file'}); continue
            if split.fragment and target in parsers:
                anchors_checked += 1
                if split.fragment not in parsers[target].ids: unresolved.append({'page':p.name,'url':url,'reason':'missing anchor'})
    report={'local_pages':len(parsers),'local_anchor_links_checked':anchors_checked,'unresolved':unresolved,
            'contents_sections':len(SECTIONS),'resources':17,'embedded_videos':3,
            'export_policy':'Explicit allowlist: no credentials, private DB, HAR, paid course transcripts or large Blender/GLB source files'}
    write_json(RECORDS/'link-audit.json',report)
    if unresolved:
        print(json.dumps(unresolved[:30],ensure_ascii=False))
        raise SystemExit('Fix unresolved document links before publishing')
    return report


def main():
    for folder in (DEST,DEST/'references',DEST/'assets',DEST/'videos',DEST/'data',RECORDS,DOC_MEDIA):
        folder.mkdir(parents=True,exist_ok=True)
    state=snapshot(); write_json(RECORDS/'state-snapshot.json',state); write_json(DEST/'data/state-snapshot.json',state)
    copy_media()
    text=add_generated_content()
    build_pages(text)
    report=copy_data_and_validate()
    (DEST/'README.txt').write_text('Tripothon 제작 현황·자료·실행 계획 / 2026-10-03\n\nindex.html을 브라우저에서 여세요. 요약·목차·선별 문서·사진·영상은 오프라인에서 볼 수 있습니다.\n기존 보고서 웹 링크는 원래 127.0.0.1:8842 서버가 필요합니다. 공식 영상·문서는 인터넷 연결이 필요합니다.\n개인 DB·API 키·유료 강의 원문·전체 게임 에셋은 포함하지 않습니다.\n참고 문서는 작성 당시 버전의 기록입니다. 현재 상태는 통합 문서의 요약·현황표를 우선합니다.\n',encoding='utf-8')
    bundle=REVIEW/'Tripothon_Master_Handoff_20261003.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(DEST.rglob('*')):
            if p.is_file(): z.write(p,Path('Tripothon_Master_Handoff_20261003')/p.relative_to(DEST))
    with zipfile.ZipFile(bundle) as z:
        damaged=z.testzip()
        if damaged: raise RuntimeError('Bundle CRC failed')
    report.update({'bundle_bytes':bundle.stat().st_size,'bundle_sha256':digest(bundle),'bundle_crc':'pass'})
    write_json(RECORDS/'link-audit.json',report)
    print(json.dumps({'url':LOCAL_URL,'source':str(SOURCE),'html':str(DEST/'index.html'),'bundle':str(bundle),**report},ensure_ascii=False))


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
