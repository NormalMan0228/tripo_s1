import json,struct,shutil,html
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/characters/explorer_b_face_refined_v2'
DEST=ROOT/'artifacts/production-lab-20261003/review/character-face-refined';DEST.mkdir(exist_ok=True)
path=OUT/'explorer_b_face_refined_v2.glb';data=path.read_bytes();length,kind=struct.unpack_from('<II',data,12);gltf=json.loads(data[20:20+length]);binary=data[28+length:]
def accessor(index):
    a=gltf['accessors'][index];view=gltf['bufferViews'][a['bufferView']];offset=view.get('byteOffset',0)+a.get('byteOffset',0)
    return np.frombuffer(binary,dtype=np.float32,count=a['count'],offset=offset)
animation=gltf['animations'];assert len(animation)==1
channels=[]
for c in animation[0]['channels']:
    s=animation[0]['samplers'][c['sampler']];values=accessor(s['output']);times=accessor(s['input']);name=gltf['nodes'][c['target']['node']]['name']
    channels.append({'node':name,'path':c['target']['path'],'weight_min':float(values.min()),'weight_max':float(values.max()),'seconds':float(times[-1]-times[0])})
assert len(channels)==6 and all(c['weight_max']>.5 for c in channels)
colors={m['name']:all('COLOR_0' in p['attributes'] for p in m['primitives']) for m in gltf['meshes'] if m['name'] in ['Face_Skin_Stitched_Geometry','Eye_L_Geometry','Eye_R_Geometry']}
assert len(colors)==3 and all(colors.values())
export={'file_bytes':len(data),'mesh_count':len(gltf['meshes']),'animation_count':len(animation),'animation_name':animation[0]['name'],'channels':channels,'face_and_eye_vertex_colors':colors,'runtime_play_test':False}
(OUT/'glb-verification.json').write_text(json.dumps(export,indent=2),encoding='utf-8')
verification=json.loads((OUT/'validation-report.json').read_text());build=json.loads((OUT/'build-report.json').read_text())
names=['front-neutral','front-bare','angle-neutral','side-neutral','blink-closed','mouth-open','angle-mouth-open']
for name in names:shutil.copy2(OUT/(name+'.png'),DEST/(name+'.png'))
for name in ['build-report.json','validation-report.json','glb-verification.json','glb-roundtrip.json','explorer_b_face_refined_v2.glb','face-performance.mp4','face-performance.webm']:
    shutil.copy2(OUT/name,DEST/name)
bare=(OUT/'face-performance-bare.mp4').exists()
if bare:shutil.copy2(OUT/'face-performance-bare.mp4',DEST/'face-performance-bare.mp4')
if (OUT/'face-performance-bare.webm').exists():shutil.copy2(OUT/'face-performance-bare.webm',DEST/'face-performance-bare.webm')
shutil.copy2(ROOT/'art/references/explorer_b_modular_v1/final_images/01_head.png',DEST/'reference-head.png')
shutil.copy2(ROOT/'art/characters/explorer_b_face_structure_v1/face-front.png',DEST/'previous-front.png')
def figure(name,caption):return f'<figure><a href="{name}.png" target="_blank"><img loading="lazy" src="{name}.png" alt="{caption}"></a><figcaption>{caption}</figcaption></figure>'
page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>얼굴 v2 · 실제 표정 변형</title><style>
:root{--ink:#293532;--muted:#69756e;--paper:#f3f0e9;--line:#dadfd7;--green:#426b59}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 system-ui,"Malgun Gothic",sans-serif}main{max-width:1260px;padding:32px 24px 72px;margin:auto}h1{font-size:37px;line-height:1.35;margin:10px 0 22px}h2{font-size:26px;margin:0 0 16px}p{margin:8px 0 18px}a{color:#325f4b}header,section{padding:28px;border-radius:20px;background:#fffefa;border:1px solid var(--line);margin:22px 0}.tag{font-size:13px;font-weight:750;color:var(--green);letter-spacing:.08em}.hero{display:grid;grid-template-columns:1fr 1.15fr;align-items:center;gap:24px}.hero img{width:100%;border-radius:13px}.meta{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}.meta span{background:#eaf0e9;border-radius:10px;padding:8px 12px}.muted{color:var(--muted)}nav{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:9px;background:#fffefaef;backdrop-filter:blur(8px);border:1px solid var(--line);border-radius:12px;padding:12px}nav a{text-decoration:none;padding:4px 12px}section{scroll-margin-top:92px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}figure img{display:block;width:100%;border-radius:12px}figcaption{color:var(--muted);padding:8px 0 16px}video{width:100%;max-height:720px;border-radius:14px;background:#222;display:block}.note{padding:15px 18px;background:#f6eee0;border-left:4px solid #b99355;border-radius:3px}.good{padding:15px 18px;background:#eaf1eb;border-left:4px solid #64866e}.button{display:inline-block;background:var(--green);color:white;text-decoration:none;border-radius:9px;padding:10px 17px;margin:5px 8px 5px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;vertical-align:top;padding:12px 10px;border-bottom:1px solid var(--line)}details{padding:16px;background:#f0f3ee;border-radius:12px;margin:16px 0}summary{cursor:pointer;font-weight:650}code{overflow-wrap:anywhere;font-size:13px}.scroll{overflow:auto}li{margin:7px 0}.chips{display:flex;flex-wrap:wrap;gap:8px}.chips span{background:#edf0eb;border-radius:8px;padding:6px 12px}@media(max-width:750px){main{padding:12px}.hero,.grid{grid-template-columns:1fr}header,section{padding:20px}h1{font-size:28px}nav a{padding:4px 7px}}
</style></head><body><main><header class="hero"><div><div class="tag">EXPLORER B · FACE V2 · 2026.10.04</div><h1>눈꺼풀과 입이<br>실제로 움직이는 얼굴</h1><p>기존 HD 머리의 얼굴형을 바탕으로 눈 주변과 입술을 다시 구성했습니다. 눈을 감고, 한쪽 눈을 감고, 턱을 벌리고, 미소 짓는 동작을 실제 메쉬로 확인할 수 있습니다.</p><div class="meta"><span>Blender 직접 제작</span><span>추가 API 비용 0</span><span>6초 · 24fps</span></div><p class="muted">완성된 게임 캐릭터 전체가 아닌 머리 단독 작업본입니다. 기본 표정 제어를 검토한 뒤 얼굴 전체 리토폴로지와 몸 리그 연결을 진행할 단계입니다.</p><a class="button" href="#motion">실제 동작 보기</a><a href="#files">파일과 조작 방법</a></div><img src="front-neutral.png" alt="새 얼굴 정면 실제 렌더"></header>
<nav><a href="#motion">애니메이션</a><a href="#views">각도·표정</a><a href="#changes">바뀐 구조</a><a href="#check">검증</a><a href="#files">파일·사용법</a></nav>
<section id="motion"><h2>실제 Blender 타임라인 재생</h2><p>중립 → 눈 깜빡임 → 한쪽 눈 감기 → 입 벌림 → 미소 → 중립 순서입니다. 아래 영상은 이미지 생성 AI 영상이 아니라 저장된 메쉬와 표정 제어를 렌더한 결과입니다.</p>
<video controls loop muted playsinline preload="metadata" poster="front-neutral.png"><source src="face-performance.mp4" type="video/mp4">브라우저에서 영상을 재생할 수 없습니다. <a href="face-performance.mp4">MP4 열기</a></video>'''
if bare:page+='''<details><summary>헤어를 숨긴 정면 변형 검토 영상</summary><p>눈꺼풀과 입술 경계를 가리지 않은 상태입니다.</p><video controls loop muted playsinline preload="metadata" poster="front-bare.png"><source src="face-performance-bare.mp4" type="video/mp4"></video></details>'''
page+='''<p class="muted">영상은 무음입니다. 이번 동작은 Blender에서 직접 작성한 Shape Key와 제어값 애니메이션이며 Tripo 자동 리깅·자동 애니메이션을 사용하지 않았습니다.</p></section>
<section id="views"><h2>형상과 변형을 따로 확인</h2><div class="grid">'''
page+=figure('front-bare','헤어를 숨긴 중립 얼굴')+figure('reference-head','승인된 입력 레퍼런스 · 얼굴 인상 비교')+figure('blink-closed','양쪽 눈 완전히 감기')+figure('mouth-open','턱 벌림 · 연결된 입술과 실제 치아')+figure('angle-neutral','사선 · 중립')+figure('side-neutral','측면 · 얼굴 깊이와 헤어 맞춤')
page+='''</div><details><summary>이전 시험본 보기</summary><p>이전 결과는 비교용으로 보존했습니다. 촬영 크기와 조명은 서로 다릅니다.</p>'''+figure('previous-front','이전 얼굴 구조 시험본')+'''</details></section>
<section id="changes"><h2>이번에 고친 구조</h2><div class="scroll"><table><tr><th>부분</th><th>변경 내용</th></tr>
<tr><td>눈 주변</td><td>생성된 눈 표면 조각을 제거하고 얼굴에 이어지는 눈꺼풀 띠를 구성했습니다. 경계의 뒤집힘과 접힘을 정리하고 연결부에 제한적으로 스무딩을 적용했습니다.</td></tr>
<tr><td>눈 감기</td><td>좌우를 독립 제어합니다. 중간 단계에서 눈꺼풀이 눈알을 파고들지 않도록 궤적 보정 Shape Key를 함께 사용합니다. 속눈썹도 같은 제어를 따릅니다.</td></tr>
<tr><td>입과 치아</td><td>닫힌 생성 표면에 실제 개구부를 만들고 입술 두께와 입 안쪽을 연결했습니다. 위·아래 치열, 잇몸, 혀는 별도 메쉬이며 아래쪽 파츠는 턱 벌림을 함께 따릅니다.</td></tr>
<tr><td>머리카락</td><td>추가했던 매끈한 덮개 대신 기존 헤어 메쉬를 두피에 맞췄습니다. 측면의 급격한 변형 경계도 완화했습니다.</td></tr>
<tr><td>재사용</td><td>피부와 홍채의 색을 정점색으로 기록했습니다. Blender 제어값은 GLB에서 재생 가능한 모프 애니메이션으로 샘플링해 하나의 클립으로 내보냈습니다.</td></tr></table></div>
<p class="note">세부 눈꺼풀 두께·눈꼬리, 눈썹 가장자리, 헤어 표면은 추가 다듬기가 가능합니다. 새 눈·입 주변에는 연결된 띠 구조를 만들었지만 얼굴 나머지 영역은 작업용 삼각형 메쉬입니다. 제작용 UV와 얼굴 전체 리토폴로지가 완료된 상태는 아닙니다.</p></section>
<section id="check"><h2>확인한 범위</h2><ul><li>저장된 Blender 파일을 다시 열어 얼굴 피부가 하나의 연결 성분인지 확인했습니다.</li><li>눈 중심부를 좌우 각각 425개 광선으로 검사했습니다. 완전히 감은 상태에서 눈알이 노출된 지점은 각각 0개였습니다.</li><li>눈 감기 0·25·50·75·100%에서 변형된 눈꺼풀 정점과 눈알 표면의 간격을 검사했습니다.</li><li>타임라인 첫 프레임과 마지막 프레임의 얼굴 정점 차이는 0이며 제어값은 0~1 범위였습니다.</li><li>GLB에는 11개 메쉬와 1개 애니메이션이 있습니다. 얼굴·속눈썹·아래 잇몸·아래 치아·혀의 6개 모프 채널이 함께 재생되도록 구성했습니다.</li><li>원본 HD 머리·헤어 파일의 해시가 유지됨을 확인했습니다.</li></ul><p class="good">현재 확인은 Blender 렌더·메쉬 수치·내보낸 GLB 구조를 대상으로 합니다. 몸 리그에 붙인 상태나 실제 Godot 플레이 중의 검증까지 수행한 것은 아닙니다.</p><details><summary>작업·검증 기록</summary><p><a href="build-report.json">제작 기록</a> · <a href="validation-report.json">얼굴 변형 검사</a> · <a href="glb-verification.json">GLB 검사</a></p></details></section>
<section id="files"><h2>파일과 조작 방법</h2><a class="button" download href="explorer_b_face_refined_v2.glb">애니메이션 포함 GLB 다운로드</a><a class="button" download href="face-performance.mp4">MP4 다운로드</a><p>편집용 Blender 파일:</p><code>C:\\lsm26\\triphthonS1\\art\\characters\\explorer_b_face_refined_v2\\explorer_b_face_refined_v2.blend</code><ol><li>Blender에서 <b>Space</b>를 누르면 1~144프레임을 재생합니다.</li><li>Outliner에서 <b>FACE_CONTROLS</b>를 선택하고 Object Properties의 Custom Properties를 보면 제어값이 있습니다.</li><li>직접 포즈를 잡을 때는 해당 제어의 애니메이션을 일시적으로 끄거나 수정할 프레임에 키를 넣습니다. 타임라인 애니메이션이 활성화된 상태에서는 프레임을 이동하면 기록된 값이 다시 적용됩니다.</li><li>새 눈꺼풀과 입 구조는 <b>Face_Skin</b>, 눈알은 <b>Eye_L / Eye_R</b>, 치아와 혀는 <b>03_ORAL_PARTS</b> 컬렉션에서 선택합니다.</li></ol><div class="chips"><span>Blink_L</span><span>Blink_R</span><span>Jaw_Open</span><span>Smile</span><span>Brow_Raise</span></div><p class="muted">GLB 클립 이름은 Scene입니다. 표정 52종이나 발음별 입 모양은 포함하지 않습니다. Blender 파일 내부의 READ_ME_FACE_V2에도 사용법을 남겼습니다.</p></section></main></body></html>'''
page=page.replace('<source src="face-performance.mp4"','<source src="face-performance.webm" type="video/webm"><source src="face-performance.mp4"')
page=page.replace('<source src="face-performance-bare.mp4"','<source src="face-performance-bare.webm" type="video/webm"><source src="face-performance-bare.mp4"')
page=page.replace('<li>원본 HD 머리·헤어 파일의 해시가 유지됨을 확인했습니다.</li>','<li>내보낸 GLB를 Blender에 다시 불러와 눈 감기와 턱·아래 치아 움직임, 시작·끝 포즈 일치를 확인했습니다.</li><li>원본 HD 머리·헤어 파일의 해시가 유지됨을 확인했습니다.</li>')
page=page.replace('<a href="glb-verification.json">GLB 검사</a>','<a href="glb-verification.json">GLB 검사</a> · <a href="glb-roundtrip.json">GLB 재불러오기 검사</a>')
(DEST/'index.html').write_text(page,encoding='utf-8')
old=ROOT/'artifacts/production-lab-20261003/review/character-face-structure/index.html'
content=old.read_text(encoding='utf-8')
if 'character-face-refined' not in content:
    content=content.replace('<body><main>','<body><main><p style="padding:18px;background:#dcecdc;border-radius:12px"><b>새 얼굴 작업본이 있습니다.</b> <a href="../character-face-refined/">얼굴 v2와 실제 표정 애니메이션 보기 →</a></p>',1)
    old.write_text(content,encoding='utf-8')
print(json.dumps(export,ensure_ascii=False,indent=2));print(DEST/'index.html')
