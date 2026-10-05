"""Package the independently generated 2D character references for human review.

This script only lays out/copies existing images. It never generates meshes,
calls a paid service, approves a production phase, or modifies source pixels.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "art/references/explorer_b_modular_v1/02_parts"
MANIFEST = PARTS / "generation-manifest-v1.json"
PLAN = ROOT / "art/characters/explorer_b_modular_v1/production-plan.json"
DESIGN = ROOT / "art/references/explorer_b_modular_v1/01_design/explorer_b_turnaround_v1.png"
REVIEW = ROOT / "artifacts/production-lab-20261003/review/character-parts-2d"
DOC = ROOT / "docs/CHARACTER_PART_REFERENCES_20261003.md"
URL = "http://127.0.0.1:8842/character-parts-2d/"
ZIP = REVIEW.parent / "Tripothon_Part_References_2D_v1_20261003.zip"
CATEGORIES = {"body": "신체", "hair": "헤어", "clothing": "의상", "accessory": "장식"}
NOTES = {
    "head-front": "얼굴 인상·귀·두상과 세 시점의 일관성을 확인합니다. 눈알·눈썹·입 안은 아직 독립 참조가 없습니다.",
    "neck": "아래쪽 쇄골 부분이 몸통과 겹칩니다. 목 길이와 최종 분할 경계를 검토해야 합니다.",
    "torso": "긴 목과 딱딱한 접합 테두리를 없앤 v2를 기본으로 표시합니다. 초기 v1도 보관했습니다.",
    "pelvis": "허벅지 연결 부분이 긴 편입니다. 골반과 허벅지의 최종 경계는 미확정입니다.",
    "upper-arm-r": "한쪽 위팔 후보입니다. 접합 원형 표시는 형상 참고이며, 최종 관절이나 접합 치수가 아닙니다.",
    "forearm-r": "팔꿈치·손목의 두께와 테이퍼를 검토합니다. 좌우 반사와 신체 연결은 3D에서 검증합니다.",
    "hand-r-dorsal": "손등·손바닥에서 다섯 손가락을 확인합니다. 정확한 측면을 추가했고 초기 3/4 시점도 남겼습니다.",
    "thigh-r": "옷 아래 허벅지의 기본 형상입니다. 골반·무릎 경계와 전체 길이는 조립 단계에서 맞춥니다.",
    "calf-r": "무릎 아래 종아리의 기본 형상입니다. 무릎·발목 경계와 좌우 대응은 미검증입니다.",
    "foot-r": "발가락 다섯 개와 발목·발등 형태를 확인합니다. 파일명의 R만으로 해부학적 좌우가 확정되지는 않습니다.",
    "hair": "머리 피부 없이 헤어만 새로 생성했습니다. 앞·뒤 형태를 비교합니다. 앞머리와 옆머리는 아직 묶음 참조입니다.",
    "jacket-body": "소매와 신체를 제거한 재킷 몸판입니다. 앞·뒤를 비교하고 소매 결합부는 추후 맞춥니다.",
    "jacket-sleeve-r": "말아 올린 소매와 소매단의 묶음 참조입니다. 어깨 개구부·안쪽 두께는 3D에서 확인해야 합니다.",
    "shirt": "재킷 아래 가려진 소매는 원안으로 확정할 수 없어 민소매 후보로 만들었습니다. 형태 검토가 필요합니다.",
    "pants": "벨트·부츠·카고 주머니를 제외한 바지 기본형입니다. 허리·다리·밑단은 이후 편집 단위로 나눕니다.",
    "boot-r": "부츠 형상 참조입니다. 끈·금속 부속·밑창은 함께 그려져 있으며 아직 각각의 독립 생성 결과가 아닙니다.",
    "belt": "버클과 분리한 짙은 갈색 벨트입니다. 허리 둘레와 버클 결합 위치는 조립 때 맞춥니다.",
    "buckle": "벨트 없이 버클만 새로 생성했습니다. 프레임·핀 형상과 벨트 폭을 검토합니다.",
    "cargo-pocket": "바지에서 독립시킨 주머니 후보입니다. 부착 위치·크기와 좌우 반사는 아직 미확정입니다.",
}

CSS = r"""
:root{--ink:#203635;--muted:#63746d;--accent:#1f6857;--paper:#fff;--line:#dfe5db;--bg:#f4f4ee;--gold:#ad7830}*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:92px}body{margin:0;background:var(--bg);color:var(--ink);font-family:'Malgun Gothic',system-ui,sans-serif;line-height:1.7}
a{color:var(--accent);text-underline-offset:3px}button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #c89c48;outline-offset:3px}
header,main,footer{max-width:1320px;margin:auto;padding:0 36px}.brand{letter-spacing:3px;font-size:11px;color:var(--muted);padding-top:28px}.topline{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}
h1{font-size:34px;letter-spacing:-1px;line-height:1.3;margin:18px 0 10px}.intro{max-width:770px;font-size:15px;color:var(--muted);margin:0 0 24px}.badge{display:inline-block;font-size:12px;background:#f4e7cb;color:#835822;padding:7px 12px;border-radius:20px;white-space:nowrap;margin-top:20px}
.steps{display:flex;gap:8px;flex-wrap:wrap;font-size:12px;margin:16px 0 26px}.steps span{padding:7px 13px;border:1px solid var(--line);border-radius:6px;color:var(--muted)}.steps .done{background:#e7eee5}.steps .active{background:var(--accent);color:white;border-color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}.stats div{background:white;padding:14px 20px;border:1px solid var(--line);border-radius:10px}.stats strong{font-size:25px;display:block;line-height:1.4}.stats small{color:var(--muted);font-size:12px}
.summary{background:#e9eee3;border-left:4px solid var(--accent);padding:16px 20px;border-radius:0 10px 10px 0;font-size:14px;margin-bottom:22px}.summary p{margin:5px 0}.jump{display:flex;flex-wrap:wrap;gap:16px;font-size:13px;margin:20px 0}
details{background:white;border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:18px 0}summary{cursor:pointer;color:var(--accent);font-weight:700;font-size:14px}.design{display:block;width:100%;max-width:1050px;margin:16px auto;border-radius:8px}.fine{font-size:12px;color:var(--muted)}
.filters{position:sticky;top:0;z-index:5;background:#f4f4eef5;backdrop-filter:blur(12px);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 0;margin:28px 0 22px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.filters button{border:1px solid var(--line);border-radius:25px;background:white;padding:7px 16px;color:var(--ink);font-size:13px}.filters button[aria-pressed=true]{background:var(--accent);color:white;border-color:var(--accent)}.filters small{margin-left:auto;color:var(--muted)}
h2{font-size:24px;margin:28px 0 6px}h2 small{font-size:12px;font-weight:400;color:var(--muted);margin-left:10px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.card{background:white;border:1px solid var(--line);border-radius:12px;overflow:hidden;min-width:0;display:flex;flex-direction:column}
.image-button{width:100%;display:block;background:white;border:0;padding:12px 14px 0;position:relative}.image-button img{width:100%;height:235px;object-fit:contain;display:block;transition:transform .2s}.image-button:hover img{transform:scale(1.035)}.count{position:absolute;top:12px;right:12px;background:#edf2e8ed;padding:3px 8px;border-radius:20px;font-size:11px;color:var(--accent)}
.card-body{padding:16px;display:flex;flex:1;flex-direction:column}.card h3{margin:0;font-size:17px}.meta{font-size:11px;color:var(--muted);margin:4px 0 9px}.note{font-size:12px;color:var(--muted);margin:0 0 14px;flex:1}.open{border:1px solid var(--line);border-radius:6px;background:#f5f7f0;padding:7px 10px;color:var(--accent);font-size:12px;text-align:left}
[hidden]{display:none!important}.review-notes{margin-top:40px}.review-notes ol{padding-left:22px;font-size:14px;line-height:1.9}.review-notes li{margin:9px 0}.tools{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}.tools a{border:1px solid #b7c7b5;border-radius:7px;background:white;padding:9px 15px;text-decoration:none;font-size:13px}
footer{padding-top:24px;padding-bottom:38px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);margin-top:36px}
dialog{border:0;padding:0;border-radius:14px;width:min(1240px,94vw);height:92vh;height:92dvh;background:#f8f9f4;color:var(--ink);box-shadow:0 20px 100px #0a241840;overflow:hidden}dialog::backdrop{background:#15271dcc;backdrop-filter:blur(5px)}
.viewer-head{display:flex;align-items:center;gap:15px;border-bottom:1px solid var(--line);padding:14px 20px;height:62px;background:white}.viewer-head h2{margin:0;font-size:19px;flex:1}.viewer-head button{border:1px solid var(--line);border-radius:6px;background:white;padding:6px 12px;font-size:12px}
.viewer-layout{display:grid;grid-template-columns:minmax(0,1fr) 295px;height:calc(100% - 62px)}.image-pane{overflow:auto;display:grid;place-items:center;background:white;min-width:0;min-height:0;padding:20px}.image-pane img{max-width:100%;max-height:100%;object-fit:contain;display:block;width:auto;height:auto}.image-pane.actual{display:block}.image-pane.actual img{max-width:none;max-height:none}
.viewer-side{overflow:auto;border-left:1px solid var(--line);padding:20px}.viewer-side p{font-size:12px;color:var(--muted)}.viewtabs{display:grid;gap:7px}.viewtabs button,.zoom button{background:white;border:1px solid var(--line);padding:8px 10px;border-radius:6px;font-size:12px;color:var(--ink);text-align:left}.viewtabs button[aria-pressed=true]{border-color:var(--accent);background:#e5ede0;color:var(--accent)}.zoom{display:flex;gap:7px;margin:18px 0 8px}.zoom button[aria-pressed=true]{background:var(--accent);color:white}.viewer-side a{font-size:12px;display:block;overflow-wrap:anywhere;margin:12px 0}.viewer-side details{padding:10px;margin-top:15px}.viewer-side summary{font-size:12px}.viewer-side pre{font-size:10px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}.viewer-side h3{font-size:13px;margin:0 0 10px}
@media(max-width:1100px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.image-button img{height:225px}}
@media(max-width:780px){header,main,footer{padding-left:18px;padding-right:18px}h1{font-size:27px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.image-button img{height:200px}.stats{grid-template-columns:repeat(2,1fr)}.topline{display:block}.badge{margin-top:0}.viewer-layout{grid-template-columns:1fr;grid-template-rows:minmax(0,1fr) 240px}.viewer-side{border-left:0;border-top:1px solid var(--line);padding:14px}.viewtabs{display:flex;flex-wrap:wrap}.viewer-head{padding:10px}.viewer-head h2{font-size:15px}.viewer-head button{padding:5px 8px}.filters small{display:none}}
@media(max-width:480px){.image-button img{height:160px}.card-body{padding:12px}.card h3{font-size:15px}.filters button{padding:6px 12px}.stats div{padding:12px 15px}.note{font-size:11px}}
@media print{.filters,.open,.tools,dialog{display:none}.grid{grid-template-columns:repeat(4,1fr)}.card{break-inside:avoid}.image-button img{height:135px}header,main,footer{padding:0}.note{font-size:10px}.summary{background:white}.stats{margin:10px 0}}
"""

JS = r"""
const groups=JSON.parse(document.getElementById('catalog').textContent);
const dialog=document.getElementById('viewer'), pane=document.getElementById('image-pane'), picture=document.getElementById('viewer-image');
let current=0, variant=0, opener=null;
function showVariant(index){
  const g=groups[current]; variant=index; const a=g.images[index]; picture.src='images/'+a.file; picture.alt=g.label+' / '+a.view;
  document.getElementById('original-link').href='images/'+a.file;
  document.getElementById('original-link').textContent='원본 PNG 열기 · '+a.pixels.join(' × ');
  document.getElementById('variant-caption').textContent=a.view+' · 검토 대기';
  document.getElementById('prompt').textContent=a.prompt;
  document.querySelectorAll('.viewtabs button').forEach((b,i)=>b.setAttribute('aria-pressed',i===index));
  setZoom(false);pane.scrollTop=0;pane.scrollLeft=0;
}
function showGroup(index){
  current=(index+groups.length)%groups.length; const g=groups[current];
  document.getElementById('viewer-title').textContent=(current+1)+' / '+groups.length+' · '+g.label;
  document.getElementById('part-note').textContent=g.note;
  document.getElementById('part-units').textContent='후속 편집 단위: '+g.parts.join(', ');
  const tabs=document.getElementById('viewtabs'); tabs.replaceChildren();
  g.images.forEach((a,i)=>{const b=document.createElement('button');b.type='button';b.textContent=a.view;b.addEventListener('click',()=>showVariant(i));tabs.append(b);});
  showVariant(0);
}
function setZoom(actual){pane.classList.toggle('actual',actual);document.getElementById('fit').setAttribute('aria-pressed',!actual);document.getElementById('actual').setAttribute('aria-pressed',actual);}
document.querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>{opener=b;showGroup(Number(b.dataset.open));dialog.showModal();}));
document.getElementById('close').addEventListener('click',()=>dialog.close());
dialog.addEventListener('close',()=>opener?.focus());
document.getElementById('previous').addEventListener('click',()=>showGroup(current-1));
document.getElementById('next').addEventListener('click',()=>showGroup(current+1));
document.getElementById('fit').addEventListener('click',()=>setZoom(false));
document.getElementById('actual').addEventListener('click',()=>setZoom(true));
dialog.addEventListener('keydown',e=>{if(e.key==='ArrowRight'){e.preventDefault();showVariant((variant+1)%groups[current].images.length);}if(e.key==='ArrowLeft'){e.preventDefault();showVariant((variant-1+groups[current].images.length)%groups[current].images.length);}});
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{
  const category=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',x===b));
  document.querySelectorAll('[data-category]').forEach(section=>section.hidden=category!=='all'&&section.dataset.category!==category);
  document.getElementById('shown-count').textContent=(category==='all'?groups.length:groups.filter(g=>g.category===category).length)+'종 표시';
}));
"""


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path):
    return path.relative_to(ROOT).as_posix()


def contact_sheet(groups):
    # Review document layout: resize thumbnails on a new canvas, original PNGs unchanged.
    width, card_w, card_h, gap, margin = 1800, 332, 355, 18, 34
    canvas = Image.new("RGB", (width, 1690), "#f4f4ee")
    draw = ImageDraw.Draw(canvas)
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    title_font = ImageFont.truetype(str(font_path), 37)
    label_font = ImageFont.truetype(str(font_path), 23)
    small_font = ImageFont.truetype(str(font_path), 18)
    draw.text((margin, 24), "B형 탐험가 · 부위별 2D 검토", fill="#203635", font=title_font)
    draw.text((margin, 78), "19종 / 총 27장 중 기본 시점 모음 · 독립 이미지의 크기는 실제 조립 비율이 아닙니다", fill="#63746d", font=small_font)
    for i, g in enumerate(groups):
        x, y = margin + (i % 5) * (card_w + gap), 127 + (i // 5) * (card_h + gap)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), 12, fill="white", outline="#dfe5db")
        with Image.open(PARTS / g["images"][0]["file"]) as original:
            thumb = ImageOps.contain(original.convert("RGB"), (card_w - 26, card_h - 92), Image.Resampling.LANCZOS)
            canvas.paste(thumb, (x + (card_w - thumb.width) // 2, y + 10 + (card_h - 92 - thumb.height) // 2))
        draw.text((x + 15, y + card_h - 66), f"{i + 1:02d}  {g['label']}", font=label_font, fill="#203635")
        draw.text((x + 15, y + card_h - 32), f"{CATEGORIES[g['category']]} · {len(g['images'])}시점/안", font=small_font, fill="#63746d")
    draw.text((margin, 1640), "2D 형상 검토 대기 · 3D 생성 / UV / 조립 / 리깅은 아직 시작하지 않았습니다", font=small_font, fill="#63746d")
    path = REVIEW / "contact-sheet-v1.jpg"
    canvas.save(path, quality=94, subsampling=0)
    return path


def make_html(groups):
    counts = {c: sum(g["category"] == c for g in groups) for c in CATEGORIES}
    filters = '<button type="button" data-filter="all" aria-pressed="true">전체 19</button>'
    filters += "".join(f'<button type="button" data-filter="{c}" aria-pressed="false">{label} {counts[c]}</button>' for c, label in CATEGORIES.items())
    sections = []
    for category, label in CATEGORIES.items():
        cards = []
        for i, g in enumerate(groups):
            if g["category"] != category:
                continue
            a = g["images"][0]
            cards.append(f'''<article class="card" id="part-{g['id']}">
<button class="image-button" type="button" data-open="{i}" aria-label="{escape(g['label'])} 이미지 확대"><img src="images/{a['file']}" alt="{escape(g['label'])} · {escape(a['view'])}" width="{a['pixels'][0]}" height="{a['pixels'][1]}"><span class="count">{len(g['images'])}시점/안</span></button>
<div class="card-body"><h3>{i+1:02d} {escape(g['label'])}</h3><p class="meta">{escape(a['view'])} · 검토 대기</p><p class="note">{escape(g['note'])}</p><button class="open" type="button" data-open="{i}" aria-label="{escape(g['label'])} 시점 비교">확대·시점 비교 ↗</button></div></article>''')
        sections.append(f'<section id="{category}" data-category="{category}"><h2>{label}<small>{counts[category]}종</small></h2><div class="grid">'+"".join(cards)+"</div></section>")
    catalog = json.dumps(groups, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>B형 탐험가 · 부위별 2D 검토</title><style>{CSS}</style></head><body>
<header><div class="brand">TRIPOTHON / CHARACTER PRODUCTION / 2026.10.03</div><div class="topline"><div><h1>B형 탐험가 · 부위별 이미지</h1><p class="intro">승인한 전신 원안을 바탕으로 신체·헤어·의상·장식 이미지를 각각 새로 생성했습니다. 부품을 눌러 원본을 확대하고 보조 시점과 수정안을 비교할 수 있습니다.</p></div><span class="badge">2단계 · 사용자 검토 대기</span></div>
<div class="steps" aria-label="제작 단계"><span class="done">01 전신 원안 승인</span><span class="active">02 부위별 2D 검토</span><span>03 부위별 3D 생성</span><span>04 모델·UV·재질</span><span>05 리깅·애니메이션</span></div>
<div class="stats"><div><strong>19종</strong><small>부품 그룹</small></div><div><strong>27장</strong><small>기본 19 + 보조 6 + 수정 2</small></div><div><strong>0</strong><small>이번 Tripo·Scenario 호출</small></div><div><strong>검토 대기</strong><small>3D 생성 승인 전</small></div></div>
<div class="summary"><p><b>지금 확인할 것:</b> 얼굴·손·헤어 형태, 몸체 분할 경계, 재킷·셔츠·바지·부츠의 디자인.</p><p>각 이미지는 독립적으로 화면을 채운 참조입니다. 이미지 크기가 실제 신체 비율을 뜻하지 않으며, 접합 치수·좌우 대칭·옷 안쪽·3D 형상은 아직 검증되지 않았습니다.</p></div>
<nav class="jump" aria-label="목차"><a href="#body">신체</a><a href="#hair">헤어</a><a href="#clothing">의상</a><a href="#accessory">장식</a><a href="#review-points">검토 항목</a><a href="#records">생성 기록</a></nav>
<details><summary>승인한 전신 2D 원안 보기</summary><img class="design" src="images/explorer_b_turnaround_v1.png" alt="승인한 B형 탐험가 전신 원안 · 정면 우측면 후면"><p class="fine">사용자의 “다음 단계로” 지시로 1단계 승인 기록을 남겼습니다. 부위별 2D 이미지의 승인은 아직 받지 않았습니다.</p></details></header>
<main><div class="filters" aria-label="부품 분류">{filters}<small id="shown-count">19종 표시</small></div>{''.join(sections)}
<section class="review-notes" id="review-points"><h2>이번 검토에서 결정할 항목</h2><ol><li><b>얼굴과 헤어:</b> 기존 B형의 인상과 둥근 두상·단발 실루엣이 맞는지 확인합니다. 헤어 앞·뒤 참조는 독립 생성이므로 동일한 3D 구조라는 보장은 없습니다.</li><li><b>신체 분할:</b> 목 아래 쇄골과 몸통, 골반과 허벅지에 겹치는 부분이 있습니다. 접합부의 원형 표시는 참고 형상입니다. 실제 피부 경계는 연속된 면과 웨이트로 정리해야 합니다.</li><li><b>손:</b> 손등·손바닥에서 다섯 손가락과 엄지 방향을 확인하고 새 정확한 측면으로 손의 두께를 비교합니다. 초기 3/4 시점은 보관한 대안입니다.</li><li><b>속옷이 아닌 겉의 기본 셔츠:</b> 원안의 재킷 아래 소매 구조가 가려져 있어 현재는 아이보리 민소매 후보입니다. 원하시는 셔츠 형태에 맞춰 이 단계에서 수정할 수 있습니다.</li><li><b>후속 세분화:</b> 19종은 60개 계획 편집 단위의 독립 이미지 60장을 뜻하지 않습니다. 헤어 묶음·소매단·바지·부츠 부속은 아직 묶음 참조이며, 눈알·눈썹·치아·혀의 개별 참조는 남아 있습니다.</li></ol><p class="fine">사용자 검토를 받은 뒤 필요한 2D 수정과 부족한 세부 참조를 보완하고, 별도 승인된 범위에서 부위별 3D 생성으로 진행합니다. 이 페이지에 자동 생성·승인 동작은 없습니다.</p></section>
<section id="records"><h2>생성 기록과 원본</h2><p>built-in image_gen으로 27번 생성했습니다. 도구가 실제 모델 ID와 별도 과금액을 공개하지 않아 임의의 모델명·비용을 붙이지 않았습니다. 이번 작업의 Tripo·Scenario 크레딧 소비는 각각 0입니다.</p><div class="tools"><a href="../../Tripothon_Part_References_2D_v1_20261003.zip">원본·프롬프트 ZIP</a><a href="CHARACTER_PART_REFERENCES_20261003.md">검토 문서 Markdown</a><a href="manifest.json">27장 명세 JSON</a><a href="contact-sheet-v1.jpg" target="_blank" rel="noopener">19종 한눈에 보기</a><a href="../master-handoff/index.html#character">통합 인계 문서</a></div><p class="fine">ZIP을 풀면 이 페이지를 오프라인으로 열 수 있습니다. 원본 PNG·이미지별 프롬프트·해시를 포함하며 계정 키나 DB는 포함하지 않습니다.</p></section></main>
<footer>전신 원안은 승인됨 · 부위별 2D는 검토 대기 · 새 3D·UV·리깅·애니메이션 산출물은 아직 없습니다.</footer>
<dialog id="viewer" aria-labelledby="viewer-title"><div class="viewer-head"><h2 id="viewer-title">부품 검토</h2><button id="previous" type="button" aria-label="이전 부품">← 이전</button><button id="next" type="button" aria-label="다음 부품">다음 →</button><button id="close" type="button">닫기</button></div><div class="viewer-layout"><div class="image-pane" id="image-pane"><img id="viewer-image" alt=""></div><aside class="viewer-side"><h3>시점·수정안</h3><div class="viewtabs" id="viewtabs"></div><p id="variant-caption"></p><div class="zoom"><button id="fit" type="button" aria-pressed="true">화면에 맞춤</button><button id="actual" type="button" aria-pressed="false">100% 확대</button></div><a id="original-link" href="#" target="_blank" rel="noopener">원본 PNG</a><p id="part-note"></p><p id="part-units"></p><details><summary>전체 생성 프롬프트</summary><pre id="prompt"></pre></details><p>← → 시점 전환 · Esc 닫기</p></aside></div></dialog>
<script type="application/json" id="catalog">{catalog}</script><script>{JS}</script></body></html>'''.replace('../../Tripothon_Part_References_', '../Tripothon_Part_References_')


def make_doc(groups):
    rows = []
    for g in groups:
        images = " / ".join(f"[{a['view']}](../art/references/explorer_b_modular_v1/02_parts/{a['file']})" for a in g["images"])
        rows.append(f"| {CATEGORIES[g['category']]} | {g['label']} | {images} | {g['note']} |")
    return f'''# B형 탐험가 — 부위별 2D 이미지 검토

기준일 **2026년 10월 3일**. 현재 단계는 **부위별 2D 참조 제작 / 사용자 검토 대기**입니다.

<a id="summary"></a>
## 요약

전신 원안은 사용자의 **“다음 단계로”** 지시로 승인 기록을 남겼습니다.
그 원안을 입력하여 신체·헤어·의상·장식 **19종, 총 27장**을 각각 생성했습니다.
기본 19장에 보조 시점 6장, 손 측면과 몸통 경계 수정 2장을 추가했습니다.
몸통은 **v2를 우선 표시**하고 초기 v1도 보관합니다.

[부품 확대·시점 비교 페이지]({URL})에서 검토할 수 있습니다.
**새 3D 생성·UV·Blender 조립·리깅·애니메이션은 아직 진행하지 않았습니다.**
이번 Tripo·Scenario 호출과 크레딧 소비는 각각 **0**입니다.

![19종 부위별 2D 참조 모음](../artifacts/production-lab-20261003/review/character-parts-2d/contact-sheet-v1.jpg)

<a id="contents"></a>
## 목차

1. [19종 참조와 보조 시점](#parts)
2. [현재 확인한 차이·미확정 사항](#review)
3. [60개 제작 단위와의 관계](#coverage)
4. [도구·비용·기록](#accounting)
5. [검토 후 다음 작업](#next)

<a id="parts"></a>
## 19종 참조와 보조 시점

이미지는 기존 전신 그림을 자른 결과가 아니라, 승인한 원안을 참고해 각 부품을 다시
생성한 결과입니다. 다만 몸통 v2는 이번에 독립 생성한 몸통 v1을 수정한 이미지입니다.
옷 아래 가려진 신체는 무채색 마네킹 형상으로 만들었습니다.
이미지마다 프레임을 채우므로 서로의 픽셀 크기는 실제 조립 비율이 아닙니다.

| 분류 | 부품 | 원본·시점 | 검토 사항 |
|---|---|---|---|
{chr(10).join(rows)}

<a id="review"></a>
## 현재 확인한 차이·미확정 사항

- **목·몸통:** 목의 쇄골 아래와 몸통 영역이 겹칩니다. 몸통 v2는 긴 목과 단단한 테두리를 제거했습니다. 최종 경계·목 길이·치수는 아직 측정하지 않았습니다.
- **골반·허벅지:** 골반의 허벅지 연결 부분이 길어 보입니다. 전체 몸체에서 경계를 정해야 합니다.
- **손:** 손등·손바닥에서 다섯 손가락을 확인했습니다. 첫 측면 요청은 3/4로 생성되어 실제 측면을 추가했습니다. 리깅·가동 범위·좌우 반사는 아직 검증하지 않았습니다.
- **셔츠:** 재킷 아래 소매가 보이지 않아 민소매 후보를 제안했습니다. 원안과 확정된 동일 구조라고 단정하지 않습니다.
- **옷·부츠:** 안쪽 두께·개구부·기본 신체와의 간격·복장 교체는 아직 2D 이미지로 검증할 수 없습니다.
- **좌우:** 한쪽을 후보로 생성했지만 이미지의 R 표기만으로 해부학적 좌우가 검증된 것은 아닙니다. 3D에서 엄지·발 형태와 좌표를 확인한 다음 반사합니다.
- **접합:** 생성 이미지의 원형 연결 끝은 참조 형상입니다. 최종 피부 관절을 기계적인 연결부로 만든다는 뜻이 아닙니다.

<a id="coverage"></a>
## 60개 제작 단위와의 관계

기존 계획의 60개 항목은 최종 편집 단위입니다. 이번 19종은 그 항목을 지원하는
이미지 그룹이며 **60개 독립 메시나 60장 독립 부품 이미지가 완료된 상태가 아닙니다.**

손은 다섯 손가락이 있는 한쪽 손을 기준으로 만들고 이후 손바닥·각 손가락을 편집 단위로
구성합니다. 헤어의 앞머리·옆머리, 소매단, 바지 허리·다리·밑단, 부츠 끈·밑창·부속은
아직 묶음 참조입니다. 필요하면 3D 생성 전에 별도 확대·부품 참조를 추가합니다.

눈알·눈썹은 얼굴 이미지에서 인상을 참고할 수 있지만 개별 참조가 없습니다.
치아·혀 참조도 아직 없습니다. 머리의 정면·측면·후면은 독립 생성 결과이므로
정확하게 동일한 3D 두상의 투영이라고 보장하지 않습니다.

제작 계획의 각 항목에 이미지 대응과 `reference_status`를 기록했습니다.
모든 `mesh_path`는 여전히 null이고 형상 검수·치수·대칭 수치는 미완료입니다.

<a id="accounting"></a>
## 도구·비용·기록

| 항목 | 이번 작업 |
|---|---|
| 이미지 생성 | built-in image_gen, 27번 호출 |
| 실제 모델 ID | 도구가 공개하지 않음. 특정 GPT 이미지 모델명으로 추정하지 않음 |
| 이미지 생성 별도 금액 | 도구가 공개하지 않음. 무료로 단정하지 않음 |
| Tripo API | 신규 호출 0, 크레딧 소비 0 |
| Scenario | 신규 호출 0, 크레딧 소비 0 |
| 별도 GPT API | 신규 호출 없음 |
| 원본 처리 | PNG 원본을 복사·검증. 검토 모음은 별도 문서 레이아웃이며 원본 픽셀을 수정하지 않음 |

- 입력 원안: `art/references/explorer_b_modular_v1/01_design/explorer_b_turnaround_v1.png`
- 원본 27장: `art/references/explorer_b_modular_v1/02_parts/`
- 목록·해시·시점·검토 상태: 같은 폴더의 `generation-manifest-v1.json`
- 전체 프롬프트·입력 경로: 같은 폴더의 이미지별 `*-generation-v1.json`
- 생성 도구가 반환한 실제 파일을 복사하는 도구: `tools/collect_part_reference_images.py`
- 검토 페이지 생성 도구: `tools/build_part_reference_review.py`
- [오프라인 검토 ZIP](../artifacts/production-lab-20261003/review/Tripothon_Part_References_2D_v1_20261003.zip): 원본 PNG, 프롬프트, 명세, 이 문서, HTML 포함. 계정 키·DB·유료 강의 원문 미포함.

<a id="next"></a>
## 검토 후 다음 작업

먼저 얼굴·헤어·손 형태, 목/몸통과 골반/허벅지 분할, 셔츠 종류와 의상 실루엣을
검토받습니다. 필요한 수정과 세부 참조가 승인된 뒤 **부위별 3D 생성**을 시작합니다.
소수 부품으로 생성 품질·비용을 확인하고 신체→의상→장식 순으로 확장합니다.
생성 결과의 대칭·치수·접합과 독립 편집 구조를 Blender에서 확인한 뒤 UV·리깅으로 진행합니다.

단계 승인 없이 후속 3D·리깅·애니메이션으로 자동 진행하지 않습니다.

- [부위별 제작 기준](CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003.md)
- [기존 생성·애니메이션 실험 기록](CHARACTER_ANIMATION_WORKFLOW_20261003.md)
- [통합 인계 문서](TRIPOTHON_MASTER_HANDOFF_20261003.md#character)

[요약으로 돌아가기](#summary)
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    active_plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if active_plan.get("reference_revision") == "simple_v2":
        raise RuntimeError("The 19-group reference package is historical. Current references: 02_parts_simple_v2; use preview_simple_parts.py.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["assets"]) == 27, "Unexpected catalog size; review new entries first."
    manifest.update(status="awaiting_user_review", approval=None,
                    primary_component_groups=19, image_count=27,
                    accounting={"image_gen_calls":27,"new_tripo_calls":0,"new_tripo_credits":0,
                                "new_scenario_calls":0,"new_scenario_credits":0,
                                "image_generation_price":"not_exposed_by_tool"})
    for asset in manifest["assets"]:
        if asset["id"] == "hand-r-side":
            asset.setdefault("requested_view", asset["view"])
            asset["view"] = "3/4 시점（초기 측면 요청）"
        if asset["id"] == "hair":
            asset.setdefault("requested_view", asset["view"])
            asset["view"] = "앞쪽（정면에 가까운 시점）"
        source = PARTS / asset["file"]
        with Image.open(source) as img:
            img.verify()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == asset["sha256"], asset["id"]
        assert asset["state"] == "saved", asset["id"]
    images_dir = REVIEW / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for primary in (a for a in manifest["assets"] if not a.get("variant_of")):
        variants = [primary] + [a for a in manifest["assets"] if a.get("variant_of") == primary["id"]]
        preferred = manifest.get("preferred_variants", {}).get(primary["id"], primary["id"])
        variants.sort(key=lambda a:a["id"] != preferred)
        groups.append({"id":primary["id"],"label":primary["label"],"category":primary["category"],
                       "parts":primary["parts"],"note":NOTES[primary["id"]],"images":variants})
    assert len(groups) == 19
    for asset in manifest["assets"]:
        shutil.copy2(PARTS / asset["file"], images_dir / asset["file"])
    shutil.copy2(DESIGN, images_dir / DESIGN.name)
    contact_sheet(groups)
    (REVIEW / "index.html").write_text(make_html(groups), encoding="utf-8")
    DOC.write_text(make_doc(groups), encoding="utf-8")
    portable_doc = DOC.read_text(encoding="utf-8").replace("../art/references/explorer_b_modular_v1/02_parts/", "images/").replace("../artifacts/production-lab-20261003/review/character-parts-2d/contact-sheet-v1.jpg", "contact-sheet-v1.jpg")
    for name in ["CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003", "CHARACTER_ANIMATION_WORKFLOW_20261003", "TRIPOTHON_MASTER_HANDOFF_20261003"]:
        portable_doc = portable_doc.replace(name + ".md", "http://127.0.0.1:8842/master-handoff/references/docs--" + name + ".html")
    (REVIEW / DOC.name).write_text(portable_doc, encoding="utf-8")
    write_json(REVIEW / "manifest.json", manifest)
    # Portable generation records retain prompts and project-relative inputs,
    # but do not publish the per-user generated-image cache path.
    for asset in manifest["assets"]:
        record = json.loads((PARTS / asset["generation_record"]).read_text(encoding="utf-8"))
        record.pop("generated_source", None)
        record.update(file="../images/" + asset["file"], sha256=asset["sha256"], pixels=asset["pixels"])
        write_json(REVIEW / "records" / asset["generation_record"], record)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    plan["state"] = "part_references_awaiting_user_review"
    plan["active_stage"] = "references"
    for stage in plan["stages"]:
        if stage["id"] == "references":
            stage["state"] = "awaiting_user_review"
            stage["evidence"] = [relative(MANIFEST)]
            stage["outputs"] = [relative(REVIEW / "index.html"), relative(DOC)] + [relative(PARTS / a["file"]) for a in manifest["assets"]]
            stage["review"].update(approved=False, approval_evidence=None)
    for part in plan["parts"]:
        matches = [a for a in manifest["assets"] if part["id"] in a["parts"]]
        part["reference_images"] = [relative(PARTS / a["file"]) for a in matches]
        part["reference_status"] = "group_reference_awaiting_review" if matches else "no_independent_reference_yet"
        assert part["mesh_path"] is None, "Do not overwrite existing geometry state."
    plan["reference_coverage_note"] = "19 image groups / 27 images are not 60 independent part images or completed meshes; eyeballs, eyebrows and mouth interior have no independent references."
    write_json(PLAN, plan)
    write_json(MANIFEST, manifest)
    zip_files = sorted(p for p in REVIEW.rglob("*") if p.is_file() and p.name != "ui-verification.json")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in zip_files:
            archive.write(path, "character-parts-2d/" + path.relative_to(REVIEW).as_posix())
        archive.write(PLAN, "production-plan.json")
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
    print(json.dumps({"groups":len(groups),"images":len(manifest["assets"]),"status":manifest["status"],
                      "review_url":URL,"review_file":relative(REVIEW / "index.html"),
                      "doc":relative(DOC),"zip_bytes":ZIP.stat().st_size,
                      "new_tripo_calls":0,"new_scenario_calls":0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
