"""Build the newcomer guide and a read-only, allowlisted local review copy."""
from __future__ import annotations

import hashlib
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re

import markdown

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/TRIPOTHON_OVERVIEW_20261004.md"
OUTPUT = SOURCE.with_suffix(".html")
REVIEW = ROOT / "artifacts/production-lab-20261003/review/project-overview"

CSS = """
:root{color-scheme:light;--ink:#192e3d;--muted:#506576;--line:#dce5ea;--teal:#12695d;--paper:#fff;--bg:#f1f5f5}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.85 'Malgun Gothic','Apple SD Gothic Neo',sans-serif;word-break:keep-all;overflow-wrap:break-word}
a{color:#12695d;text-underline-offset:3px}a:hover{color:#93491a}aside{position:fixed;inset:0 auto 0 0;width:270px;background:#163e3d;color:#edf7f4;padding:30px 22px;overflow-y:auto}aside a{color:#edf7f4;text-decoration:none}aside .brand{font-size:24px;font-weight:800;letter-spacing:.03em}aside .meta{color:#b8d6ce;font-size:12px;margin:6px 0 24px}.toc ul{padding:0;list-style:none}.toc li{margin:9px 0;font-size:13px;line-height:1.6}.toc a{display:block;padding:5px 9px;border-radius:6px}.toc a:hover{background:#2d5853;color:white}.toc ul ul{display:none}.toc>ul>li>ul{display:block}.toc>ul>li>a{display:none}
main{margin:0 0 0 270px;padding:48px 4vw 80px;max-width:1510px}article{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:42px 44px;box-shadow:0 8px 32px #163e3d06}.eyebrow{font-size:12px;font-weight:bold;letter-spacing:.15em;color:var(--teal)}h1{font-size:40px;line-height:1.3;margin:14px 0 20px;letter-spacing:-.045em}h2{font-size:26px;line-height:1.5;margin:64px 0 18px;padding-top:22px;border-top:2px solid var(--line);letter-spacing:-.035em}h3{font-size:19px;margin-top:34px}p{margin:15px 0}li{margin:8px 0}strong{font-weight:750}code{font:13px/1.6 Consolas,monospace;background:#edf2f5;padding:2px 5px;border-radius:4px;word-break:break-word}pre{padding:22px;background:#eff5f3;border:1px solid #d4e4de;border-radius:10px;overflow:auto;line-height:1.75;word-break:normal;white-space:pre}pre code{background:none;padding:0;font-size:14px;word-break:normal}.table-wrap{overflow-x:auto;margin:20px 0;border:1px solid var(--line);border-radius:10px}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.8;min-width:580px}th{text-align:left;background:#e8f1ee;font-weight:750;color:#214e45;padding:13px 15px}td{padding:14px 15px;border-top:1px solid var(--line);vertical-align:top}tr:nth-child(even) td{background:#fafcfc}td:first-child{min-width:118px}blockquote{margin:20px 0;border-left:4px solid #d5a554;background:#fff9ed;padding:8px 20px}.actions{display:flex;gap:16px;font-size:13px;margin:20px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:25px 0}.card{background:#eaf3ef;border-radius:10px;padding:20px}.card small{display:block;color:#4b6b60}.card b{display:block;font-size:19px;margin:3px 0}.card span{font-size:13px;line-height:1.65;display:block}.diagram{margin:22px 0;padding:22px;background:#f6f9f9;border:1px solid var(--line);border-radius:12px}.flow{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap}.node{border:1px solid #bad7cc;border-radius:8px;background:white;padding:14px 16px;flex:1;min-width:130px}.node b{display:block;color:#155e50}.node small{display:block;font-size:12px;color:var(--muted);line-height:1.6}.arrow{align-self:center;color:#447f70;font-weight:bold}.group{border:1px dashed #98b5ac;border-radius:10px;padding:17px;margin-top:15px}.group-title{font-size:12px;font-weight:bold;margin-bottom:12px;color:#58736b}.diagram .note{font-size:12px;margin:12px 0 0;color:#567066}.subflow{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.flow-label{font-size:12px;color:#5a6f79;margin-bottom:9px;font-weight:bold}.footer{font-size:12px;color:var(--muted);margin-top:28px}.source-view{white-space:pre-wrap;word-break:break-word;max-width:100%}.back{display:block;margin-bottom:20px}
@media(max-width:1150px){aside{width:230px;padding:24px 16px}main{margin-left:230px;padding:25px 22px}article{padding:30px 26px}h1{font-size:32px}.cards{grid-template-columns:1fr}.card{padding:14px 18px}}
@media(min-width:781px) and (max-width:1000px){aside{position:static;width:auto;max-height:220px;padding:16px 24px}.toc>ul>li>ul{columns:3}.toc li{margin:3px 0;font-size:12px}.toc{margin-top:8px}aside .brand{font-size:19px}aside .meta{margin:2px 0;display:none}main{margin:0;padding:18px}.cards{grid-template-columns:repeat(3,1fr)}.card b{font-size:16px}.card{padding:14px}.node{min-width:100px}.table-wrap table{min-width:0}.toc ul{margin:0}}
@media(max-width:780px){aside{position:static;width:auto;max-height:260px}main{margin:0;padding:16px 10px}article{padding:25px 18px;border-radius:10px}h1{font-size:29px}h2{font-size:23px}.subflow{grid-template-columns:1fr}.arrow{display:none}table{font-size:13px}.toc>ul>li>ul{columns:2}.cards{gap:8px}}
@media print{aside,.actions{display:none}body{background:white;font-size:10pt}main{margin:0;padding:0;max-width:none}article{border:0;box-shadow:none;padding:0}h1{font-size:25pt}h2{font-size:17pt;margin-top:28px;break-after:avoid}h3{break-after:avoid}table{min-width:0;font-size:9pt}td,th{padding:7px}tr,.card,.node{break-inside:avoid}.table-wrap{overflow:visible}pre{white-space:pre-wrap}a{color:inherit}.cards{grid-template-columns:repeat(3,1fr)}}
"""

ARCHITECTURE = """<div class="diagram" role="img" aria-label="Godot 클라이언트가 HTTPS로 Caddy와 FastAPI에 연결하고, 서버가 SQLite, 자산 파일, 외부 생성 서비스를 관리합니다.">
<div class="flow-label">플레이어의 요청과 응답</div>
<div class="flow"><div class="node"><b>Godot 클라이언트</b><small>화면 · 입력 · UI · 동작 재생</small></div><span class="arrow">↔ HTTPS ↔</span><div class="node"><b>Caddy</b><small>온라인 HTTPS 연결 입구</small></div><span class="arrow">↔</span><div class="node"><b>FastAPI 서버</b><small>인증 · 규칙 · 보상 · 소유권</small></div></div>
<div class="group"><div class="group-title">FastAPI가 접근하고 관리하는 것</div><div class="subflow"><div class="node"><b>SQLite DB</b><small>계정 · 잔액 · 진행 · 소유권<br>파일 경로 · 작업 상태</small></div><div class="node"><b>개인 자산 파일</b><small>생성된 GLB와 부품<br>권한 확인 후 클라이언트에 전달</small></div><div class="node"><b>외부 생성 서비스</b><small>LLM: 계획 · 제한된 동작 정의<br>Tripo: 3D 모델 생성</small></div></div></div>
<div class="group"><div class="group-title">별도로 진행하는 개발용 아트 제작</div><div class="flow"><div class="node"><b>Blender</b><small>형태 · 리깅 · 애니메이션 편집</small></div><span class="arrow">→ GLB →</span><div class="node"><b>game/assets</b><small>배포 게임에 포함되는 공용 자산</small></div></div></div>
<p class="note">로컬 개발은 Caddy 없이 FastAPI에 연결할 수 있습니다. DB와 외부 서비스 비밀 키는 클라이언트에 전달하지 않습니다.</p></div>"""

LOOP = """<div class="diagram" role="img" aria-label="마을 생활, 7일 생존, 별씨 보상, AI 가구 제작과 꾸미기를 반복합니다."><div class="flow"><div class="node"><b>01 마을 생활</b><small>농사 · 낚시 · NPC</small></div><span class="arrow">→</span><div class="node"><b>02 생존 도전</b><small>탐험 · 채집 · 전투</small></div><span class="arrow">→</span><div class="node"><b>03 별씨 보상</b><small>서버가 결과를 판정</small></div><span class="arrow">→</span><div class="node"><b>04 만들고 꾸미기</b><small>AI 공방 · 색칠 · 배치</small></div></div><p class="note">꾸민 마을에서 다시 생활하고 다음 생존 도전에 나섭니다.</p></div>"""

def page(body: str, toc: str, title: str, extra: str = "") -> str:
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title><style>{CSS}</style></head><body><aside><div class="brand">TRIPOTHON</div><div class="meta">처음 만나는 프로젝트<br>2026.10.04 기준</div>{toc}</aside><main><article><div class="eyebrow">PROJECT GUIDE / DEVELOPMENT &amp; PRODUCTION</div>{extra}{body}</article><div class="footer">저장소의 코드·기록을 기준으로 작성한 로컬 안내서입니다. 상태 표시는 작성 기준일에 해당합니다.</div></main></body></html>'''


class LinkReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href" and v)


def main():
    source = SOURCE.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"], extension_configs={"toc": {"toc_depth": "1-2"}})
    body = md.convert(source)
    body = re.sub(r"<table>(.*?)</table>", r'<div class="table-wrap"><table>\1</table></div>', body, flags=re.S)

    def diagram(match):
        text = match.group(0)
        if "Caddy:" in text and "플레이어 PC" in text:
            return ARCHITECTURE
        if "마을 생활" in text and "성과 보상" in text:
            return LOOP
        return text

    body = re.sub(r"<pre><code.*?</code></pre>", diagram, body, flags=re.S)
    cards = '''<div class="cards"><div class="card"><small>게임의 중심</small><b>생활 → 생존 → 꾸미기</b><span>보상이 AI 가구와 내 공간의 변화로 이어집니다.</span></div><div class="card"><small>최신 로컬 결과</small><b>최대 3인 협동</b><span>마을 방문·협동 생존 검증. 원격 배포는 별도입니다.</span></div><div class="card"><small>현재 캐릭터 방향</small><b>Tripo 모델 → 애드온 리깅</b><span>Tripo로 생성하고 Blender에서 다듬은 뒤 페이스 리깅에 애드온을 사용합니다.</span></div></div>'''
    body = body.replace("<h2", cards + "<h2", 1)
    local_actions = '<div class="actions"><a href="TRIPOTHON_OVERVIEW_20261004.md">편집 가능한 Markdown</a><a href="javascript:window.print()">인쇄 / PDF 저장</a></div>'
    OUTPUT.write_text(page(body, md.toc, "Tripothon 한눈에 이해하기", local_actions), encoding="utf-8")

    # Serve only the guide and its explicitly linked source files, never the workspace root.
    (REVIEW / "references").mkdir(parents=True, exist_ok=True)
    reader = LinkReader()
    reader.feed(body)
    links = sorted({x for x in reader.links if not x.startswith(("#", "https:", "http:"))})
    mapped: dict[str, str] = {}
    for href in links:
        path = (SOURCE.parent / href.split("#", 1)[0]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"Missing or invalid source link: {href}")
        if path.suffix not in {".md", ".json", ".py", ".gd"}:
            raise ValueError(f"Source type not allowlisted: {path}")
        name = hashlib.sha256(href.encode()).hexdigest()[:12] + ".html"
        rel = "references/" + name
        content = path.read_text(encoding="utf-8-sig")
        code = f'<a class="back" href="../index.html">← 안내서로 돌아가기</a><h1>{escape(path.name)}</h1><p>{escape(path.relative_to(ROOT).as_posix())}</p><pre class="source-view">{escape(content)}</pre>'
        (REVIEW / rel).write_text(page(code, '<a href="../index.html">전체 안내서</a>', path.name), encoding="utf-8")
        mapped[href] = rel
    review_body = re.sub(r'href="([^"]+)"', lambda m: f'href="{mapped.get(m[1], m[1])}"', body)
    (REVIEW / "index.html").write_text(page(review_body, md.toc, "Tripothon 한눈에 이해하기", local_actions), encoding="utf-8")
    (REVIEW / SOURCE.name).write_text(source, encoding="utf-8")
    print(f"Guide: {OUTPUT}")
    print(f"Review: {REVIEW / 'index.html'}")
    print(f"Verified local source links: {len(links)}")
    print(f"Sections: {len(re.findall(r'^## ', source, re.M))}")


if __name__ == "__main__":
    main()
