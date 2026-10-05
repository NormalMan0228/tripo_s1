"""Publish actual Blender stills and evidence for the face construction study."""
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_face_structure_v1'
DEST=ROOT/'artifacts/production-lab-20261003/review/character-face-structure'
DEST.mkdir(parents=True,exist_ok=True)
for name in ['face-front','face-angle','face-side','body-fit-front','body-fit-angle','mouth-layout-cutaway']:
    shutil.copy2(OUT/(name+'.png'),DEST/(name+'.png'))
for name in ['construction-report.json','delivery-verification.json']:
    shutil.copy2(OUT/name,DEST/name)
shutil.copy2(ROOT/'art/characters/explorer_b_hd_restart_v1/head/preview-front.png',DEST/'source-head.png')
shutil.copy2(ROOT/'art/references/explorer_b_modular_v1/final_images/01_head.png',DEST/'reference-head.png')
verification=json.loads((OUT/'delivery-verification.json').read_text(encoding='utf-8'))
def figure(name,caption):
    return f'<figure><a href="{name}.png" target="_blank"><img src="{name}.png" alt="{caption}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>'
html='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HD 얼굴 · 구조 제작 시험</title><style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eff1f2;color:#29343b;font:16px/1.75 system-ui,"Malgun Gothic",sans-serif}main{max-width:1280px;margin:auto;padding:24px 24px 80px}header,section{background:#fff;border:1px solid #dbe1e4;padding:28px;border-radius:16px;margin-bottom:24px}h1{font-size:34px;margin:8px 0}h2{font-size:25px;margin-top:0}h3{font-size:19px}a{color:#195f72}nav{position:sticky;top:0;z-index:2;background:#fffffff5;padding:12px;display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px;border-radius:10px;border:1px solid #dbe1e4}nav a{text-decoration:none;padding:3px 10px}section{scroll-margin-top:110px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.wide{grid-column:1/-1}.tag{color:#647c86;font-weight:700}.note{background:#f8f1e6;border-left:4px solid #c69345;padding:14px 18px}.good{background:#eef4f4;padding:14px 18px;border-radius:10px}figure{margin:0}figure img{width:100%;display:block;border-radius:10px}figcaption{margin:7px 0 18px;color:#526670}table{width:100%;border-collapse:collapse}th,td{padding:12px;border-bottom:1px solid #dce3e6;text-align:left;vertical-align:top}code{font-size:13px;word-break:break-all}.scroll{overflow:auto}.steps{display:flex;gap:10px;flex-wrap:wrap}.steps span{padding:9px 14px;border:1px solid #dbe1e4;border-radius:8px}.steps .current{background:#dae9e9;font-weight:700}li{margin:7px 0}@media(max-width:700px){main{padding:12px}.grid{grid-template-columns:1fr}header,section{padding:20px}h1{font-size:27px}}
</style></head><body><main>
<header><div class="tag">2026.10.04 · 실제 Blender 작업본 · 추가 API 비용 0</div><h1>HD 얼굴 구조를 먼저 검토합니다</h1>
<p>기존 HD 신체·머리·헤어를 사용해 머리를 교체하고, 생성 메쉬에 붙어 있던 눈 표면을 독립된 좌우 눈알로 바꿨습니다. 얼굴 피부·코·눈꺼풀·입술은 하나의 연결된 피부 메쉬로 유지했습니다. 치아·잇몸·혀·입 안쪽은 별도 오브젝트로 배치했습니다.</p>
<p class="note"><b>얼굴 구조 제작 시험입니다.</b> 눈 경계와 목 연결, 헤어 안쪽은 추가 정리가 필요합니다. 입술은 아직 닫힌 생성 형상이며 입을 열 수 없습니다. 리토폴로지·표정 리그·Shape Key·애니메이션은 제작하지 않았습니다. 의상과 교체 손·신발의 최종 조립도 이번 얼굴 시험에 포함되지 않습니다.</p>
<p><a href="../character-hd-restart/">기존 HD 7개 파츠</a> · <a href="construction-report.json">작업 기록</a> · <a href="delivery-verification.json">저장 파일 검증</a></p>
</header>
<nav><a href="#face">얼굴</a><a href="#parts">파츠 구성</a><a href="#mouth">입 안 배치</a><a href="#body">신체 비율</a><a href="#sources">자료와 적용</a><a href="#next">검토 순서</a></nav>
<section id="face"><h2>실제 근접 렌더</h2><p>아래는 생성한 컨셉 그림이 아니라 저장된 작업본을 Blender Cycles에서 렌더한 결과입니다. 갈색 헤어와 피부색은 검토용 재질이며 UV 텍스처는 아닙니다. 눈썹·속눈썹의 표면 잡음과 눈 안쪽 절단 경계는 남아 있습니다.</p><div class="grid">'''
html+=figure('face-front','정면 · 독립 눈알과 기존 얼굴 형상')+figure('face-angle','사선 · 눈꺼풀, 코, 입술의 관계')+figure('face-side','측면 · 머리 깊이와 목 연결 검토')+figure('source-head','수정 전 HD 머리 · 다른 조명과 무채색 재질')
html+='''</div><p class="note">헤어 틈의 두피 노출은 별도의 안쪽 캡으로 덮었습니다. 캡 표면은 아직 매끈하므로 외부 머리카락 덩어리와의 연결과 가르마 디테일을 더 다듬어야 합니다. 목은 크기와 단면을 맞춘 시험 상태이며 전신과 용접하지 않았습니다.</p></section>
<section id="parts"><h2>분리한 것과 연결해 둔 것</h2><div class="scroll"><table><tr><th>구성</th><th>이번 결과</th><th>후속 작업</th></tr>
<tr><td>얼굴 피부·코·눈꺼풀·입술</td><td>Head_Skin_HD_Working · 하나의 연결된 메쉬</td><td>눈·입 주변 루프와 입술 안쪽 모델링</td></tr>
<tr><td>좌우 눈알</td><td>Eyeball_L / Eyeball_R · 같은 크기와 대칭 위치 · 절차형 홍채</td><td>눈꺼풀과의 밀착, 시선 회전 때의 교차 검증</td></tr>
<tr><td>헤어</td><td>Hair_HD_Fitted_Study / Hair_Inner_Cap_Study</td><td>안쪽 캡과 외부 덩어리의 형상·재질 통합</td></tr>
<tr><td>위·아래 치아와 잇몸</td><td>Upper / Lower Teeth / Gum · 각각 선택 가능</td><td>입을 연 상태의 맞물림·잇몸 노출 검토</td></tr>
<tr><td>혀·입 안쪽</td><td>Tongue_Layout / Mouth_Interior_Layout · 배치 시안</td><td>입술 안쪽과 연결, 턱 움직임에 맞춰 조정</td></tr>
<tr><td>신체</td><td>Body_HD_Head_Replaced_Study · 기존 머리를 작업본에서 제거</td><td>목 연결과 의상·손·신발 조립</td></tr></table></div>
<p>Blender Outliner의 01~05 컬렉션에서 구성별로 선택할 수 있습니다. 조명과 카메라는 06_Review_Studio에 있습니다. 원본 HD 파일은 수정하지 않았습니다.</p></section>
<section id="mouth"><h2>입 안 구조 · 배치 시안</h2><p class="note">피부를 렌더에서 숨겨 내부 오브젝트만 보여준 이미지입니다. 입을 실제로 벌린 표정이 아닙니다. 현재 입술에는 개구부와 안쪽 두께가 없으므로 이 오브젝트를 넣는 것만으로 말하기나 웃기가 가능해지지는 않습니다.</p><div class="grid">'''
html+=figure('mouth-layout-cutaway','위·아래 치아와 잇몸, 혀, 열린 뒷벽 배치')+figure('reference-head','승인된 머리 입력 이미지 · 얼굴 인상 비교용')
html+='''</div></section><section id="body"><h2>신체에 맞춘 크기</h2><p>1.6m를 작업 단위 기준으로 잡았습니다. 의상·피부를 구분하는 최종 텍스처 대신 신체는 회색 재질로 표시했습니다. 목의 피부색은 연결 위치 확인용입니다.</p><div class="grid">'''
html+=figure('body-fit-front','신체와 머리 비율 · 정면')+figure('body-fit-angle','신체와 머리 비율 · 사선')
html+='''</div></section><section id="sources"><h2>수집한 자료를 어떻게 적용했는가</h2>
<ul><li><b>Stefan 보유 강의:</b> Sculpting의 머리 교체·마스킹·크기와 위치 조정, Retopology의 머리와 눈 주변 수정 흐름을 작업 순서에 반영했습니다. 이번에는 Blender 스크립트로 작업했으며 수동 브러시 작업을 수행했다고 기록하지 않습니다.</li>
<li><b><a href="https://faceit-doc.readthedocs.io/en/latest/geometry/" target="_blank">Faceit 공식 Geometry 문서</a>:</b> 연결된 얼굴 피부와 별도의 눈·치아·잇몸·혀 구조를 기준으로 삼았습니다. Faceit 설치·자동 바인딩은 이번 작업에서 사용하지 않았습니다.</li>
<li><b><a href="https://www.tripo3d.ai/blog/gpt-6-astra-3d-character-workflow" target="_blank">Tripo 공식 조립·얼굴 제작 흐름</a>:</b> 신체·머리·헤어를 나눠 조립하고 각도를 바꿔 검수하는 순서를 참고했습니다. 공식 페이지의 여러 시연은 동일 프로젝트의 연속 결과가 아니라고 명시되어 있습니다.</li>
<li><b><a href="https://note.com/osushi_san/n/n0c2a7b88276f" target="_blank">お寿司職人의 제작 기록</a>:</b> 생성된 눈·입을 그대로 리깅하지 않고 Blender에서 구조를 보완하며 반복 검토한 사례입니다. Tripo 협찬 P2 사례로, 현재 우리의 HD 형상에서 같은 결과를 보장하지 않습니다.</li></ul>
<p>사용 원본은 기존 Tripo HD 출력입니다. 이번에는 새 Tripo 생성·리깅 API·텍스처 API를 호출하지 않았습니다. 검토용 색은 Blender 재질과 정점색, 홍채는 절차형 재질로 작성했습니다.</p></section>
<section id="next"><h2>이 작업본 이후의 순서</h2><div class="steps"><span class="current">① 얼굴 인상·비율 검토</span><span>② 눈·입·목 형상 수정</span><span>③ 변형용 리토폴로지</span><span>④ UV·베이크·재질</span><span>⑤ 얼굴 리그·표정</span><span>⑥ 애니메이션·Godot 검증</span></div>
<p>먼저 얼굴 인상과 눈 크기, 머리·신체 비율을 확인합니다. 이를 확정한 뒤 눈꺼풀 닫힘, 입술 개구부와 내부 두께, 목 연결을 정리합니다. 얼굴 변형용 토폴로지가 안정된 다음 표정 리그를 제작합니다.</p>
<p class="good">저장 파일을 다시 열어 메쉬 선택 가능 여부, 좌우 눈 위치, 얼굴 연결 성분, 원본 파일 해시를 확인했습니다. '''
html+=f"메쉬 {verification['mesh_objects']}개 · 얼굴 연결 성분 {len(verification['head_component_vertex_counts'])}개 · Armature 0개 · Shape Key 0개."
html+='''</p><h3>작업본 위치</h3><code>C:\\lsm26\\triphthonS1\\art\\characters\\explorer_b_face_structure_v1\\explorer_b_HD_face_structure_trial.blend</code><p>재생할 애니메이션은 없습니다. 뷰포트의 Material Preview에서 얼굴을 확인하고 Outliner에서 각 메쉬를 선택하세요.</p></section></main></body></html>'''
(DEST/'index.html').write_text(html,encoding='utf-8')
print(DEST/'index.html')
