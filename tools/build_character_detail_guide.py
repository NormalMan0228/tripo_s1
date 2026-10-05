"""Render the curated character references as a local document and review page."""
from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/character-detail-references.json"
REVIEW = ROOT / "artifacts/production-lab-20261003/review"
DEST = ROOT / "docs/AI_CHARACTER_DETAIL_REFERENCES_20261003.md"
TOPICS = {
    "parts": "파츠와 머리카락",
    "face-rig": "얼굴 리그와 표정 구조",
    "face-motion": "AI 얼굴 애니메이션",
    "hands": "손가락과 동작",
    "surface": "표면과 제작 자동화",
    "research": "모발 연구 데모",
}

INTRO = """# AI 캐릭터 세부 제작 자료집

확인일 2026년 10월 3일. 대상은 Tripothon의 B형 탐험가와 마을 NPC이며, Tripo로 모델을 다시 세부 제작한 뒤 Blender에서 리깅하고 Godot에 전달하는 개발용 작업입니다.

우리에게 가장 가까운 조합은 **Stefan의 파츠별 생성 → 얼굴 메시 정리 → Faceit으로 표정 구조 준비 → MediaPipe나 Audio2Face로 얼굴 모션 생성 → 몸·손 동작과 결합**입니다. 이 조합은 자료를 바탕으로 한 제안이며, 전체를 우리 캐릭터에서 검증한 구현 결과는 아닙니다.

## AI가 맡는 일을 먼저 구분하기

| 작업 | 자료와 도구 | 얻는 결과 | 별도로 해야 하는 일 |
| --- | --- | --- | --- |
| 부품 만들기 | Stefan, Tripo P2·Segmentation | 파츠 메시 | 크기·연결부·변형용 토폴로지 검수 |
| 표정을 만들 얼굴 준비 | CGDive·Csaba Kiss의 Faceit | shape key·얼굴 제어 구조 | 눈꺼풀·입·턱의 변형 수정 |
| 얼굴 움직임 얻기 | Audio2Face, AccuFACE, MediaPipe | 시간별 표정 값·얼굴 모션 | 대상 리그로 전이·보정·베이크 |
| 손 움직임 얻기 | cg tinker·MediaPipe | 손 랜드마크·관절 구동 | 손가락 메시·웨이트·가려짐 보정 |
| 반복 작업 자동화 | Stefan의 Claude in Blender | 스크립트·베이크·검사 자동화 | 기준 설정과 결과 검수 |

Faceit과 AccuRIG은 이 목록에서 **리깅 자동화 도구**로 다룹니다. 생성형 AI 모델과 같은 것으로 설명하지 않습니다. MediaPipe는 머신러닝으로 동작을 추정하지만, 우리 캐릭터의 얼굴 메시나 손 모델을 새로 만드는 것은 아닙니다. [Faceit 공식 문서](https://faceit-doc.readthedocs.io/en/latest/), [MediaPipe 공식 가이드](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker).

## 가장 먼저 볼 자료

1. Stefan의 Tripo Smart Mesh P2 강의 03:15–05:01: 몸 전체를 더 복잡하게 만드는 대신 파츠 단위 생성과 헤어 결과를 판단하는 기준을 봅니다.
2. CGDive의 Faceit 첫 강의: 새 얼굴에 어떤 표정 구조가 필요한지 파악합니다.
3. Csaba Kiss의 07:15–14:55 구간: 자동 바인딩·표정 오류·게임용 베이크를 봅니다.
4. cg tinker의 손·얼굴 추적과 최신 MediaPipe 문서: 기존 몸 영상 파이프라인을 확장할 무료 후보를 검토합니다.
5. NVIDIA의 Audio2Face Part 1과 Part 2: 얼굴 구조와 음성 기반 모션을 연결하는 방식을 봅니다. 예전 설치법은 현행 SDK 안내와 구분합니다.

## 자료별 정리
"""

TAIL = """
## 머리카락과 얼굴을 새로 만들 때의 적용안

아래는 자료에 근거한 **Tripothon 작업 제안**입니다.

머리카락은 우리 컨셉에 맞는 덩어리형 메시를 먼저 시험합니다. 정면 실루엣뿐 아니라 옆·뒤 모양, 두피와의 접점, 목 회전 때의 간섭을 봅니다. 가닥 복원 연구가 더 세밀한 결과를 보여도, 그대로 게임용 헤어·LOD·흔들림으로 이어지는 것은 아닙니다. Stefan의 헤어 실험과 HairStep의 결과는 서로 다른 목표로 비교해야 합니다.

얼굴 피부는 눈꺼풀·입 주변이 변형될 수 있는 일관된 메시로 준비합니다. 눈알·치아·혀·머리카락·장신구는 목적에 따라 별도 파츠로 두되, 피부 자체를 잘게 쪼개는 것을 품질 향상의 기준으로 삼지 않습니다. Tripo에서 웃는 얼굴과 화난 얼굴을 각각 새로 생성한 결과는 정점 수와 순서가 달라질 수 있어, 곧바로 shape key로 사용할 수 있다고 가정하지 않습니다. 표정은 기준 얼굴의 정점을 유지하며 만들어야 합니다. [Faceit 시작 문서](https://faceit-doc.readthedocs.io/en/latest/getting_started/).

첫 얼굴 시험은 중립·깜빡임·미소·입 벌리기·눈썹 올리기로 시작하는 것이 좋겠습니다. 얼굴 실루엣을 유지하며 눈꺼풀이 눈알을 뚫지 않고, 입 안이 찢어지지 않는지를 먼저 확인합니다. 그 다음 표정 채널을 늘리고 음성·영상 기반 얼굴 모션을 연결합니다. 기존의 걷기·달리기 몸 동작에 얼굴 모션을 더할 때는 머리 회전을 어느 쪽에서 담당할지도 정합니다.

손은 AI 생성 결과에서 손가락이 실제로 분리됐는지부터 확인합니다. 관절이 있어도 메시가 붙어 있으면 자연스럽게 움직이지 않습니다. 마디 주변의 형상·웨이트를 확보한 뒤 손 클로즈업 영상에서 동작을 추출하고, 쥐기·펴기·엄지 맞닿기·도구 잡기를 시험합니다. cg tinker의 방식은 이 동작 추출을 참고하는 자료이며, 손 모델 생성의 대체 수단은 아닙니다.

## 도구 도입 우선순위

| 선택 | 추천하는 경우 | 현재 판단 |
| --- | --- | --- |
| Tripo와 Blender 유지 | 파츠·헤어·복장 제작 | 기존 도구로 먼저 모델 품질을 높이기 |
| Faceit 검토 | 같은 얼굴에서 여러 표정과 NPC 재사용 | 상세 얼굴 리그를 위한 우선 유료 후보. 현재 Blender 버전 호환과 샘플 얼굴 결과부터 확인 |
| MediaPipe 얼굴·손 확장 | 추가 서비스 과금 없이 영상 기반 동작 실험 | 우리 기존 파이프라인과 가장 가까움. cg tinker의 구조를 참고하고 현행 Tasks API 사용 |
| Audio2Face 3D 검토 | NPC 대사에 음성 기반 얼굴 모션 추가 | 현행 SDK와 모델 조건·실행 환경 확인이 필요. 옛 GUI 설치 영상만 따라 시작하지 않기 |
| CC5·Headshot·AccuFACE 검토 | 표준 얼굴 구조와 유료 제작 생태계 도입 | AI 모델과 스타일 얼굴 변형 사례는 유용하나, Tripo 얼굴 변환·Godot 전달을 먼저 시험 |
| KeenTools 검토 | 영상 기반 얼굴 추적 비교 | FaceBuilder 토폴로지 제약이 있어 첫 도입 순위는 낮음 |
| HairStep·Neural Haircut | AI 모발 복원 원리 조사 | 연구 참고로 유지. 상용 게임용 제작 경로로 아직 채택하지 않음 |

## 버전과 이용 조건에서 확인할 부분

- NVIDIA Omniverse Launcher는 2025년 10월 1일부터 deprecated 상태이며, 설치 파일 배포와 Exchange의 앱 설치 경로가 종료됐습니다. 기존 설치는 계속 실행될 수 있습니다. 기존 Audio2Face 영상은 작업 원리를 보는 자료로 쓰고, 새 설치는 현재 저장소를 기준으로 검토해야 합니다. [NVIDIA 현행 안내](https://developer.nvidia.com/omniverse/legacy-tools).
- Audio2Face 3D SDK는 Windows·Linux와 CUDA·TensorRT 실행 환경을 요구합니다. SDK의 MIT 코드 라이선스가 모든 모델·데이터의 이용 조건을 대신하지 않습니다. RTX 2070에서의 실제 실행 속도와 품질은 이번 조사에서 측정하지 않았습니다. [공식 SDK](https://github.com/NVIDIA/Audio2Face-3D-SDK).
- BlendArMocap의 원 영상은 2022년 자료입니다. 현대 Tasks API 포크의 Blender 4.5 LTS 테스트는 유지관리자의 설명이며, 우리 환경에서의 실행 확인은 아닙니다. 오래된 영상의 관리자 권한 설치 절차를 그대로 재현할 필요가 있다고 판단하지 않습니다. [포크 README](https://github.com/Ivangeraldo/BlendArMocap-UpdatedAPIPort-2026).
- HairStep의 HiSa·HiDa 데이터와 관련 체크포인트는 비상업 연구용입니다. 무료 공개 저장소라는 이유로 상업 이용 가능하다고 분류하면 안 됩니다. Neural Haircut도 의존 모델·데이터의 조건까지 확인하기 전에는 상용 후보로 확정하지 않습니다. [HairStep 공식 저장소](https://github.com/GAP-LAB-CUHK-SZ/HairStep), [Neural Haircut 공식 코드](https://github.com/Vanessik/NeuralHaircut).
- 유료 도구를 검토할 때는 소프트웨어 사용권과 구매한 헤어·복장 등 콘텐츠의 게임 내 배포권을 구분해 확인해야 합니다. 이 자료집은 특정 콘텐츠의 상업 배포권을 판정한 문서가 아닙니다.

## 조사 범위와 확인 수준

국내외 자료를 검색했으며, 이번 목록은 얼굴·손·머리카락의 **실제 3D 데이터 제작 또는 전이 과정**을 확인할 수 있는 자료를 우선했습니다. 2D 영상에서 얼굴만 움직이는 예제, 이미지 속 헤어 변경, 출력 메시·리그가 확인되지 않는 홍보 영상은 주 추천에서 제외했습니다. 국내 채널 수를 맞추기 위해 직접 관련 없는 프리비즈 자료를 넣지는 않았습니다.

Stefan 자료는 사용자가 제공한 강의 자막과 공개 영상 자막을 읽었습니다. 다른 영상은 제작자의 설명·챕터·YouTube 제목과 채널·공식 매뉴얼·사례 글을 확인했습니다. 모든 영상을 처음부터 끝까지 프레임별로 시청했다는 뜻은 아니며, 도구를 설치해 동일 결과를 재현했다는 뜻도 아닙니다. 각 자료에 확인 범위를 표시했습니다.

강의·문서 안의 설치 지시나 도구 추천은 제3자 자료로 취급했습니다. 이번에는 자료 조사와 정리만 수행했으며, 유료 생성·도구 구매·프로젝트 모델 변경은 수행하지 않았습니다.
"""


def md_resource(r: dict, n: int) -> str:
    text = f"\n### {n:02d} {r['channel']} {r['title']}\n\n"
    text += f"[{r['title']}]({r['url']})\n\n"
    text += f"{r['priority']} · {r['kind']} · {r['access']}\n\n"
    text += f"**볼 구간:** {r['range']}\n\n"
    for label, key in [("배울 내용", "learn"), ("남는 결과", "output"), ("우리 게임에 적용", "fit"), ("한계", "limit"), ("확인 범위", "verified")]:
        text += f"**{label}:** {r[key]}\n\n"
    if r.get("local"):
        local = ROOT / r["local"]
        text += f"보유 자료: [{local.name}]({local.as_posix()})\n\n"
    if r.get("extra"):
        text += "함께 볼 자료: " + " · ".join(f"[{x['label']}]({x['url']})" for x in r["extra"]) + "\n\n"
    return text


def e(value: str) -> str:
    return html.escape(value, quote=True)


def card(r: dict, n: int) -> str:
    extra = "".join(f'<a href="{e(x["url"])}" target="_blank" rel="noopener noreferrer">{e(x["label"])} ↗</a>' for x in r.get("extra", []))
    fields = "".join(f'<div><dt>{label}</dt><dd>{e(r[key])}</dd></div>' for label, key in [("남는 결과", "output"), ("Tripothon 적용", "fit"), ("남은 작업과 한계", "limit")])
    return f'''<article class="resource" data-topic="{r['topic']}">
<div class="resource-top"><span class="number">{n:02d}</span><div><span class="channel">{e(r['channel'])}</span><h3>{e(r['title'])}</h3></div><span class="pill">{e(r['priority'])}</span></div>
<div class="badges"><span>{e(TOPICS[r['topic']])}</span><span>{e(r['kind'])}</span></div>
<p class="range">{e(r['range'])}</p><p>{e(r['learn'])}</p><dl>{fields}</dl>
<div class="links"><a class="primary" href="{e(r['url'])}" target="_blank" rel="noopener noreferrer">{'강의 사이트' if r.get('local') and 'learn3d' in r['url'] else '자료 보기'} ↗</a>{extra}</div>
<p class="verify">{e(r['access'])}<br>확인 범위: {e(r['verified'])}</p></article>'''


CSS = """
:root{--bg:#f7f4ec;--ink:#253e35;--muted:#61756c;--line:#d8ded2;--green:#2d6451;--gold:#9a7536}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 'Malgun Gothic',system-ui,sans-serif}a{color:var(--green)}header,main,footer{max-width:1190px;margin:auto;padding:0 30px}header{padding-top:48px}.eyebrow{font-size:12px;letter-spacing:2px;color:var(--muted)}h1{font-size:clamp(34px,4.5vw,55px);line-height:1.25;letter-spacing:-1.5px;margin:20px 0}h2{font-size:27px;letter-spacing:-.8px;line-height:1.4}h3{font-size:19px;line-height:1.4;margin:5px 0}.lead{font-size:19px;max-width:950px}.meta{color:var(--muted);font-size:13px}.nav{display:flex;gap:24px;flex-wrap:wrap;margin:27px 0 36px}.nav a{font-size:14px}section{margin:44px 0;scroll-margin-top:24px}.callout{background:#e8efe5;border-left:4px solid var(--green);padding:20px 24px;border-radius:0 12px 12px 0}.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0}.step{border:1px solid var(--line);background:white;border-radius:12px;padding:18px}.step small{color:var(--muted);font-size:11px}.step b{display:block;font-size:16px;line-height:1.4;margin:6px 0}.step p{font-size:13px;margin:8px 0 0}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0 14px}button{font:inherit;font-size:13px;padding:10px 15px;border:1px solid var(--line);border-radius:20px;color:var(--ink);background:white;cursor:pointer}button[aria-pressed=true]{background:var(--green);color:white;border-color:var(--green)}button:focus-visible,a:focus-visible{outline:3px solid var(--gold);outline-offset:3px}.results{font-size:13px;color:var(--muted)}.resources{display:grid;grid-template-columns:1fr 1fr;gap:20px}.resource{background:#fff;border:1px solid var(--line);border-radius:15px;padding:25px;min-width:0}.resource[hidden]{display:none}.resource-top{display:flex;gap:14px;align-items:start}.number{font-size:26px;color:#92a69a}.channel{font-size:12px;color:var(--muted)}.pill{font-size:11px;background:#f0e8d7;color:#795725;padding:3px 7px;border-radius:6px;white-space:nowrap;margin-left:auto}.badges{display:flex;gap:9px;flex-wrap:wrap;margin:14px 0}.badges span{font-size:11px;background:#eef2ec;padding:3px 8px;border-radius:6px}.range{font-size:13px;color:var(--gold);font-weight:700}.resource p{font-size:14px}.resource dl{border-top:1px solid var(--line);margin:17px 0;padding-top:13px}.resource dl div{margin:11px 0}dt{font-size:11px;color:var(--muted);font-weight:700}dd{font-size:13px;margin:3px 0 0}.links{display:flex;flex-direction:column;align-items:start;gap:8px}.links a{font-size:12px;overflow-wrap:anywhere}.links a.primary{font-size:13px;background:var(--green);color:white;border-radius:7px;text-decoration:none;padding:8px 13px}.verify{font-size:11px!important;color:var(--muted);border-top:1px solid var(--line);padding-top:13px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:22px}.note{background:#edf0e6;border-radius:12px;padding:24px}.note h3{font-size:19px;margin-top:0}.note p{font-size:14px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px;background:white}th,td{border-bottom:1px solid var(--line);padding:15px;text-align:left;vertical-align:top}th{background:#e7eee3}footer{font-size:12px;color:var(--muted);padding-top:25px;padding-bottom:45px;border-top:1px solid var(--line)}@media(max-width:850px){.resources,.columns{grid-template-columns:1fr}.flow{grid-template-columns:repeat(2,1fr)}header,main,footer{padding-left:18px;padding-right:18px}.pill{white-space:normal}.resource{padding:20px}}@media print{.filters,.nav{display:none}.resources{display:block}.resource{break-inside:avoid;margin-bottom:18px}body{background:white}}
body{word-break:keep-all;overflow-wrap:break-word}@media(max-width:1050px){.flow{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.flow{grid-template-columns:1fr}}
"""


def render_page(resources: list[dict]) -> str:
    filters = '<button type="button" data-filter="all" aria-pressed="true">전체</button>' + "".join(f'<button type="button" data-filter="{key}" aria-pressed="false">{label}</button>' for key, label in TOPICS.items())
    cards = "\n".join(card(r, n) for n, r in enumerate(resources, 1))
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 캐릭터 세부 제작 자료집</title><style>{CSS}</style></head><body>
<header><div class="eyebrow">TRIPOTHON / CHARACTER PRODUCTION RESEARCH / 2026.10.03</div><h1>파츠부터 표정까지<br>AI 캐릭터 세부 제작 자료집</h1><p class="lead">Stefan의 파츠 생성 방식에 얼굴·손·표면 제작 자료를 연결했습니다. 무엇을 AI가 만들고, 어떤 3D 데이터가 남으며, 어디에 사람의 보정이 필요한지 함께 비교합니다.</p><p class="meta">17개 자료 · 공개 영상 11개와 추가 영상 링크 · 보유 강의 3개 · 공식 파츠 가이드 · 모발 연구 2개</p><nav class="nav"><a href="#route">추천 순서</a><a href="#library">주제별 자료</a><a href="#proposal">우리 캐릭터에 적용</a><a href="#versions">버전과 확인 범위</a><a href="character-detail-references.md" download>문서 저장</a><a href="video-animations.html#compare">기존 애니메이션 비교</a></nav></header>
<main><section id="route"><h2>우리 작업에 가까운 시작점</h2><div class="callout"><b>Stefan 파츠 생성 → Faceit 표정 구조 → MediaPipe 얼굴·손 → Audio2Face 대사 모션</b><br>자료에 근거한 제작 제안입니다. 얼굴 리그 자동화와 AI 얼굴 연기는 서로 다른 단계로 봅니다.</div>
<div class="flow"><div class="step"><small>01 / GEOMETRY</small><b>파츠와 헤어 만들기</b><p>Tripo · Stefan<br>부품 메시와 연결부</p></div><div class="step"><small>02 / DEFORMATION</small><b>표정을 만들 얼굴</b><p>Faceit · Csaba Kiss<br>입·눈꺼풀·턱 변형</p></div><div class="step"><small>03 / PERFORMANCE</small><b>얼굴과 손 연기</b><p>MediaPipe · cg tinker<br>클로즈업 영상 추적</p></div><div class="step"><small>04 / DIALOGUE</small><b>대사에 맞는 모션</b><p>Audio2Face · AccuFACE<br>음성·영상 기반 표정</p></div><div class="step"><small>05 / GAME</small><b>베이크와 게임 검수</b><p>Blender → Godot<br>변형·간섭·동작 전환</p></div></div></section>
<section id="library"><h2>주제별 자료 찾기</h2><p>영상 제목과 채널, 핵심 구간을 함께 표기했습니다. 강의 자료는 보유 파일의 확인 구간을 문서에 기록했습니다.</p><div class="filters" role="group" aria-label="자료 주제 선택">{filters}</div><p class="results" id="results" aria-live="polite">전체 자료 {len(resources)}개</p><div class="resources">{cards}</div></section>
<section id="proposal"><h2>B형 탐험가에 적용할 작업 제안</h2><div class="columns"><div class="note"><h3>머리카락은 실루엣과 연결부터</h3><p>덩어리형 헤어를 먼저 시험하고 정면·옆·뒤에서 두피 접점과 목 회전 간섭을 확인합니다. 모발 가닥 복원 연구는 헤어 메시·LOD·리그까지 완성한 게임 에셋과 구분합니다.</p></div><div class="note"><h3>얼굴은 기준 메시를 유지</h3><p>새로 생성한 표정마다 정점 구조가 달라질 수 있습니다. 기준 얼굴을 고정하고 눈꺼풀·입·턱 변형을 만듭니다. 눈알·치아·혀·헤어는 별도 파츠로 관리할 수 있습니다.</p></div><div class="note"><h3>손 모델과 손 동작을 따로 검수</h3><p>손가락 분리와 마디 형상·웨이트를 먼저 확보합니다. 그 다음 손 클로즈업 영상에서 동작을 추출해 쥐기·펴기·엄지 맞닿기·도구 잡기를 확인합니다.</p></div><div class="note"><h3>첫 얼굴 시험은 작은 표정 세트</h3><p>중립·깜빡임·미소·입 벌리기·눈썹 올리기부터 검사합니다. 얼굴 실루엣을 유지하고 눈알 관통·입 찢어짐이 없으면 AI 모션을 연결하고 채널을 늘립니다.</p></div></div></section>
<section id="versions"><h2>설치 전에 구분할 부분</h2><div class="table-wrap"><table><thead><tr><th>자료</th><th>현재 확인한 조건</th><th>우리 판단</th></tr></thead><tbody><tr><td>Audio2Face 구 영상</td><td>Omniverse Launcher는 2025년 10월 1일부터 deprecated. 설치 파일과 Exchange 설치 경로 종료.</td><td>기존 설치 실행과 새 SDK 도입을 구분하고, 현행 환경·모델 조건을 검토.</td></tr><tr><td>BlendArMocap 구 영상</td><td>2022년 영상. 현대 Tasks API 포크는 Blender 4.5 LTS 시험을 주장.</td><td>포크의 실행·품질은 미검증. 기존 MediaPipe 파이프라인 확장의 참고.</td></tr><tr><td>KeenTools</td><td>추적 얼굴에 FaceBuilder 토폴로지 필요. ARKit·Rigify 전이 제공.</td><td>임의의 Tripo 얼굴을 바로 추적한다고 가정하지 않기.</td></tr><tr><td>HairStep</td><td>HiSa·HiDa 데이터와 관련 체크포인트는 비상업 연구용.</td><td>연구 데모 참고. 상용 제작 후보로 채택하지 않음.</td></tr></tbody></table></div>
<p class="meta">조건 출처: <a href="https://developer.nvidia.com/omniverse/legacy-tools" target="_blank" rel="noopener noreferrer">NVIDIA 현행 안내</a> · <a href="https://github.com/NVIDIA/Audio2Face-3D-SDK" target="_blank" rel="noopener noreferrer">공식 SDK</a> · <a href="https://github.com/Ivangeraldo/BlendArMocap-UpdatedAPIPort-2026" target="_blank" rel="noopener noreferrer">MediaPipe 포크</a> · <a href="https://keentools.io/products/facetracker-for-blender" target="_blank" rel="noopener noreferrer">KeenTools</a> · <a href="https://github.com/GAP-LAB-CUHK-SZ/HairStep" target="_blank" rel="noopener noreferrer">HairStep</a></p>
<p>Stefan 자료는 제공받은 자막을 읽었고, 다른 자료는 제작자 설명·챕터·제목·공식 문서와 사례를 확인했습니다. 모든 영상의 프레임별 시청이나 도구 실행 재현을 완료했다는 뜻은 아닙니다. 각 카드에 확인 범위를 표시했습니다.</p><p>국내외 자료를 검색했으며, 직접 관련 있는 3D 제작과 전이 과정을 우선했습니다. 2D 영상의 얼굴·헤어 변경만 보여주는 자료는 주 추천에서 제외했습니다.</p></section></main>
<footer>자료 조사와 정리 · 유료 생성 0회 · 새 도구 설치 없음<br>상세 확인 범위와 보유 강의 파일 경로는 저장 문서에 포함되어 있습니다.</footer>
<script>const buttons=[...document.querySelectorAll('[data-filter]')];const cards=[...document.querySelectorAll('[data-topic]')];buttons.forEach(button=>button.addEventListener('click',()=>{{const topic=button.dataset.filter;buttons.forEach(b=>b.setAttribute('aria-pressed',String(b===button)));let count=0;cards.forEach(card=>{{const show=topic==='all'||card.dataset.topic===topic;card.hidden=!show;if(show)count++;}});document.querySelector('#results').textContent=button.textContent+' 자료 '+count+'개';}}));</script></body></html>'''


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    resources = data["resources"]
    assert len({r["id"] for r in resources}) == len(resources)
    assert all(r["topic"] in TOPICS for r in resources)
    markdown = INTRO + "".join(md_resource(r, n) for n, r in enumerate(resources, 1)) + TAIL
    DEST.write_text(markdown, encoding="utf-8")
    REVIEW.mkdir(parents=True, exist_ok=True)
    (REVIEW / "character-detail-references.md").write_text(markdown, encoding="utf-8")
    (REVIEW / "character-detail-references.html").write_text(render_page(resources), encoding="utf-8")
    print(json.dumps({"resources": len(resources), "markdown": str(DEST), "page": str(REVIEW / "character-detail-references.html")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
