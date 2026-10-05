"""Render the video-derived motion report using existing local source recordings."""
from pathlib import Path
import json, shutil, subprocess, zipfile, sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/video-motion-20261003'
OLD=ROOT/'artifacts/production-lab-20261003'
REVIEW=OLD/'review'
DEST=REVIEW/'video-motion';DEST.mkdir(exist_ok=True)
FFMPEG=ROOT/'.tools/art-venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
manifest=json.loads((OUT/'animation-manifest.json').read_text())
audit=json.loads((OUT/'reimport-audit.json').read_text())
godot=json.loads((OUT/'godot-acceptance.json').read_text())
if not (audit['pass'] and godot['pass']):raise SystemExit('Motion acceptance must pass before report export.')

def run(args):
    subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y',*args],check=True)

def encode(stem,inputs,filters=None):
    for suffix,codec in [('webm',['-c:v','libvpx-vp9','-crf','29','-b:v','0','-row-mt','1']),
                         ('mp4',['-c:v','libx264','-profile:v','baseline','-level:v','3.1','-crf','20','-movflags','+faststart'])]:
        size='scale=1152:720:in_range=auto:out_range=tv' if stem in ('comparison-game','comparison-loops') else 'scale=iw:ih:in_range=auto:out_range=tv'
        vf=','.join(v for v in [filters,size,'format=yuv420p'] if v)
        target=OUT/f'{stem}.{suffix}'
        reuse='--reuse-media' in sys.argv or ('--only-loop-media' in sys.argv and stem!='comparison-loops')
        if not reuse or not target.exists():
            run([*inputs,'-t','5','-an','-vf',vf,'-color_range','tv','-r','30',*codec,str(target)])
        shutil.copy2(target,DEST/target.name)
    print('REVIEW_MEDIA',stem,flush=True)

frames=OUT/'final-capture/frames/frame-%04d.jpg'
encode('comparison-game',['-framerate','30','-i',str(frames)])
encode('comparison-loops',['-framerate','30','-i',str(OUT/'loops-capture/frames/frame-%04d.jpg')])
sources=[('seedance2','Seedance 2.0'),('pixverse6','PixVerse V6'),('kling3','Kling V3')]
cards=[];rows=[]
for i,(name,label) in enumerate(sources):
    encode(name+'-retarget',['-framerate','30','-i',str(frames)],f'crop=456:558:{20+470*i}:140')
    encode(name+'-reference',['-i',str(OLD/f'videos/{name}.mp4')])
    raw=json.loads((OUT/name/'landmarks-raw.json').read_text())
    sequence=manifest['clips'][name+'_sequence'];loop=manifest['clips'][name+'_loop']
    result=godot['clips'][name+'_loop'];surface=audit['clips'][name+'_loop']
    poster=OUT/f'{name}-retarget-poster.jpg'
    Image.open(OUT/'final-capture/frames/frame-0030.jpg').crop((20+470*i,140,476+470*i,698)).save(poster,quality=95)
    shutil.copy2(poster,DEST/poster.name)
    shutil.copy2(OUT/name/'track-024.jpg',DEST/f'{name}-tracking.jpg')
    segment=loop['source_segment']
    cards.append(f'''<article class="card" id="{name}"><header><span class="number">0{i+1}</span><div><h3>{label}</h3><p>영상 고유의 보폭·팔 동작·타이밍을 추출</p></div></header>
<div class="pair"><div><div class="label">입력 · AI 생성 영상</div><video id="{name}-source" controls playsinline muted preload="metadata"><source src="video-motion/{name}-reference.webm" type="video/webm"><source src="video-motion/{name}-reference.mp4" type="video/mp4"></video></div>
<div><div class="label">출력 · 실제 Godot 스켈레탈 애니메이션</div><video id="{name}-result" controls playsinline muted preload="metadata" poster="video-motion/{poster.name}"><source src="video-motion/{name}-retarget.webm" type="video/webm"><source src="video-motion/{name}-retarget.mp4" type="video/mp4"></video></div></div>
<div class="toolbar"><button data-pair="{name}">{label} 함께 재생</button><button data-stop="{name}">정지</button><output id="{name}-status" aria-live="polite">5.00초 · 준비 중</output></div>
<p class="detail">몸 관절 추적 {raw['detected_frames']}/{raw['frame_count']}프레임 · 전체 클립 5초 · 반복 클립 {loop['duration_s']:.3f}초</p>
<details><summary>관절 추적 근거 보기</summary><img src="video-motion/{name}-tracking.jpg" alt="{label} 원본 영상 위에 표시한 추적 관절"><p>녹색: 상대적으로 높은 가시성. 주황색: 가려지거나 불확실한 관절. 깊이·가려진 팔·다리는 보정값이 포함됩니다.</p></details></article>''')
    rows.append(f'<tr><td>{label}</td><td>{name}_sequence<br>{name}_loop</td><td>5.000 / {loop["duration_s"]:.3f}초</td><td>{segment["start_s"]:.3f}–{segment["end_s"]:.3f}초</td><td>{result["endpoint_rotation_gap_deg"]:.3f}°</td><td>{loop["reference_speed_mps"]:.2f}m/s 추정</td></tr>')

for path in [ROOT/'labs/video_motion_lab/assets/explorer_video_motions.glb',OUT/'explorer_video_motions.blend',OUT/'reimport-audit.json',OUT/'godot-acceptance.json']:
    shutil.copy2(path,DEST/path.name)
manifest['status']='verified in Blender GLB reimport and Godot; three separate source-derived sequences and three closed loop derivatives'
manifest['acceptance']={'godot':godot,'reimport':audit}
for name in manifest['clips']:
    if name.endswith('_loop'):manifest['clips'][name]['endpoint_correction']='distributed quaternion correction; loop closure and evaluated surface verified'
(OUT/'animation-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
shutil.copy2(OUT/'animation-manifest.json',DEST/'animation-manifest.json')
for view in ('front','back'):
    shutil.copy2(OUT/f'{view}-capture/godot-04.png',DEST/f'{view}-view.png')
shutil.copy2(OUT/'final-capture/frames/frame-0090.jpg',DEST/'comparison-poster.jpg')
shutil.copy2(OUT/'loops-capture/frames/frame-0045.jpg',DEST/'loop-poster.jpg')

# A time-aligned source/result contact sheet, composed from actual recordings.
sheet=Image.new('RGB',(1500,950),'#f5f1e7');draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
draw.text((24,15),'같은 시간의 원본 영상과 Godot 결과',font=font,fill='#304840')
for j,t in enumerate([1,2,3,4]):draw.text((130+j*340,58),f'{t:.1f}초 · 원본 / 3D',font=small,fill='#304840')
for i,(name,label) in enumerate(sources):
    y=90+i*280;draw.text((16,y+110),label,font=small,fill='#304840')
    for j,t in enumerate([1,2,3,4]):
        temp=OUT/f'{name}-source-{t}.jpg'
        if not ({'--reuse-media','--only-loop-media'} & set(sys.argv)) or not temp.exists():
            run(['-ss',str(t),'-i',str(OLD/f'videos/{name}.mp4'),'-frames:v','1','-update','1',str(temp)])
        pair=[Image.open(temp),Image.open(OUT/f'final-capture/frames/frame-{30*t:04d}.jpg').crop((20+470*i,140,476+470*i,698))]
        for k,img in enumerate(pair):
            img.thumbnail((155,255));sheet.paste(img,(135+j*340+k*165+(155-img.width)//2,y+(255-img.height)//2))
sheet.save(OUT/'source-result-contact.jpg',quality=95);shutil.copy2(OUT/'source-result-contact.jpg',DEST/'source-result-contact.jpg')

download=OUT/'Tripothon_Video_Motions_20261003.zip'
with zipfile.ZipFile(download,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
    for path in [ROOT/'labs/video_motion_lab/assets/explorer_video_motions.glb',OUT/'explorer_video_motions.blend',OUT/'animation-manifest.json',OUT/'reimport-audit.json',OUT/'godot-acceptance.json']:
        z.write(path,path.name)
    for name,_ in sources:
        z.write(OUT/name/'motion-channels.json',f'provenance/{name}/motion-channels.json')
        z.write(OUT/name/'landmarks-raw.json',f'provenance/{name}/landmarks-raw.json')
shutil.copy2(download,DEST/download.name)

page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tripothon · 영상 기반 애니메이션 3종</title>
<style>
:root{--paper:#f7f4ed;--ink:#213d35;--muted:#687a72;--line:#d9ded4;--accent:#2b6653}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Malgun Gothic",system-ui,sans-serif;line-height:1.7}main{max-width:1260px;margin:auto;padding:44px 28px 80px}a{color:var(--accent)}nav{display:flex;gap:24px;flex-wrap:wrap;font-size:14px}h1{font-size:clamp(30px,4vw,50px);letter-spacing:-1.8px;line-height:1.25;margin:20px 0}h2{font-size:27px;letter-spacing:-.7px}h3{font-size:23px;margin:0}.eyebrow{font-size:13px;letter-spacing:2px;color:var(--muted);margin-top:34px}.lead{font-size:19px;max-width:850px}.stats{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:30px 0}.stats div{padding:16px 8px}.stats strong{display:block;font-size:28px}.stats span{font-size:13px;color:var(--muted)}section{margin:44px 0}.hero-video{width:100%;border-radius:14px;background:#d3dbd1;display:block}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}button,.download{font:inherit;font-size:14px;padding:10px 17px;border-radius:8px;border:1px solid var(--line);cursor:pointer;background:white;color:var(--ink)}button:first-child,.download{background:var(--accent);color:white;border-color:var(--accent)}button:focus-visible,a:focus-visible{outline:3px solid #c89a51;outline-offset:3px}output{font-size:13px;color:var(--muted)}.card{border-top:1px solid var(--line);padding:28px 0 36px}.card header{display:flex;gap:20px;align-items:center;margin-bottom:18px}.card header p{margin:2px 0;color:var(--muted);font-size:14px}.number{font-size:35px;color:#a3b2a5;font-weight:700}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pair video{width:100%;height:450px;background:#e2e8e0;object-fit:contain;border-radius:12px}.label{font-size:13px;margin-bottom:8px}.detail{font-size:14px;color:var(--muted)}details{margin-top:18px;font-size:14px}summary{cursor:pointer}details img{display:block;max-height:520px;max-width:100%;margin-top:14px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:15px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#e7ede4}code{font-size:12px}.scroll{overflow:auto}.notes{display:grid;grid-template-columns:1fr 1fr;gap:24px}.note{background:#edf0e7;border-radius:12px;padding:22px}.note h3{font-size:18px}.note p{font-size:14px}.gallery{display:grid;grid-template-columns:1fr 1fr;gap:16px}.gallery img{width:100%;border-radius:12px}.contact{width:100%;border-radius:12px}.path{overflow-wrap:anywhere;font-size:12px;color:var(--muted)}footer{border-top:1px solid var(--line);padding-top:24px;font-size:13px;color:var(--muted)}@media(max-width:700px){main{padding:25px 16px 60px}.stats{grid-template-columns:repeat(3,1fr)}.pair,.notes,.gallery{grid-template-columns:1fr}.pair video{height:400px}h1{letter-spacing:-1px}}
</style><main><nav><a href="index.html#motion">이전 제작 문서</a><a href="#compare">원본 ↔ 3D 비교</a><a href="#loops">반복 동작</a><a href="#files">재사용 파일</a></nav>
<div class="eyebrow">TRIPOTHON / VIDEO TO ANIMATION / 2026.10.03</div><h1>세 영상에서 추출한<br>세 개의 실제 3D 애니메이션</h1><p class="lead">Seedance·PixVerse·Kling 영상의 몸 움직임을 각각 추적하고, 같은 B형 탐험가의 리그에 옮겼습니다. 아래 결과는 Godot에서 GLB를 불러와 실제로 재생한 화면입니다.</p>
<div class="stats"><div><strong>3</strong><span>서로 다른 영상 기반 클립</span></div><div><strong>6</strong><span>전체 동작 3 + 반복 동작 3</span></div><div><strong>41</strong><span>공유 리그의 뼈</span></div><div><strong>60fps</strong><span>키프레임 베이크</span></div><div><strong>0</strong><span>추가 생성 API 크레딧</span></div></div>
<section><h2>같은 캐릭터·조명·카메라에서 비교</h2><video class="hero-video" id="all-result" controls playsinline muted preload="metadata" poster="video-motion/comparison-poster.jpg"><source src="video-motion/comparison-game.webm" type="video/webm"><source src="video-motion/comparison-game.mp4" type="video/mp4"></video><div class="toolbar"><button data-single="all-result">Godot 비교 영상 재생</button><output id="all-result-status">5.00초 · 준비 중</output></div><p class="detail">5초 전체 클립은 원본 영상의 흐름을 따르는 일회성 동작입니다. 반복 재생에 사용할 클립은 아래에서 별도로 비교합니다.</p></section>
<section id="compare"><h2>원본 영상과 결과를 함께 재생</h2><p>각 버튼은 원본과 3D 결과를 0초부터 함께 재생합니다. 두 재생창을 직접 탐색하면 같은 시간으로 맞춰집니다. 옆모습의 가려진 관절과 깊이는 추정·보정했습니다.</p>__CARDS__</section>
<section id="loops"><h2>재사용할 수 있는 반복 클립</h2><video class="hero-video" id="loop-result" controls playsinline muted loop preload="metadata" poster="video-motion/loop-poster.jpg"><source src="video-motion/comparison-loops.webm" type="video/webm"><source src="video-motion/comparison-loops.mp4" type="video/mp4"></video><div class="toolbar"><button data-single="loop-result">반복 애니메이션 재생</button><output id="loop-result-status">5.00초 · 준비 중</output></div>
<div class="scroll"><table><thead><tr><th>영상</th><th>GLB 클립 이름</th><th>전체 / 반복 길이</th><th>루프 원본 구간</th><th>Godot 루프 연결점 차이</th><th>접지 속도 기준</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<p class="detail">접지 속도는 1.7배 게임 크기에서 발의 후방 이동으로 추정했습니다. 재생 속도 = 이동 속도 ÷ 접지 기준 속도로 시작할 수 있지만, 단일 영상의 추정값이므로 실제 게임 이동·경사·정지 시 발 미끄러짐을 추가 검수해야 합니다. 이번 비교는 제자리 재생이며 기존 게임의 주인공을 교체하지 않았습니다.</p></section>
<section><h2>검증한 부분과 아직 남은 부분</h2><div class="notes"><div class="note"><h3>완료한 검증</h3><p>세 전체 동작이 서로 다른 키프레임을 가집니다. GLB를 Blender와 Godot에 다시 불러왔고, 수평 루트 변위·관절 변화·반복 연결점을 검사했습니다. 0.24초 동작 전환을 30·60fps에서 검증했습니다. 재수입된 실제 스킨 표면도 10Hz와 끝 프레임에서 바닥을 뚫지 않는지 검사했습니다.</p><p>__QA__</p></div><div class="note"><h3>다음 품질 작업</h3><p>단일 옆모습 영상에서 숨겨진 깊이·가려진 관절을 정확히 복원할 수는 없습니다. 몸 동작을 추적하고 팔의 깊이·관절 한계·발바닥 높이를 보정했습니다. 손가락 개별 동작과 얼굴 표정은 추출하지 않았습니다. 물리적 모션 캡처나 완성된 상용 게임 모션으로 분류하지 않습니다.</p><p>원본 AI 영상의 팔다리 오류가 추적에도 영향을 줍니다. 여러 각도의 참고 영상과 접지 IK를 더하면 보정의 정확도를 높일 수 있습니다.</p></div></div></section>
<section><h2>정면·뒷면 및 시간별 검수</h2><div class="gallery"><figure><img src="video-motion/front-view.png" alt="Godot 정면의 세 애니메이션"><figcaption>정면 · 2.2초</figcaption></figure><figure><img src="video-motion/back-view.png" alt="Godot 뒷면의 세 애니메이션"><figcaption>뒷면 · 2.2초</figcaption></figure></div><img class="contact" src="video-motion/source-result-contact.jpg" alt="1초부터 4초까지 원본과 3D 결과를 나란히 비교한 표본"></section>
<section id="files"><h2>제작 원본과 재사용 파일</h2><div class="toolbar"><a class="download" href="video-motion/Tripothon_Video_Motions_20261003.zip" download>GLB + Blender + 추적 근거 받기</a><a href="video-motion/explorer_video_motions.glb" download>GLB</a><a href="video-motion/explorer_video_motions.blend" download>Blender 원본</a><a href="video-motion/animation-manifest.json">클립 명세</a><a href="video-motion/godot-acceptance.json">Godot 검증</a><a href="video-motion/reimport-audit.json">재수입 검증</a></div><p class="path">로컬 제작실 실행: C:\\lsm26\\triphthonS1\\Video_Motion_Lab.cmd</p><p class="detail">제작실에서 재생·정지, 타임라인, 전체/반복, 옆면/정면/뒷면을 바꿀 수 있습니다. 리그·텍스처·6개 동작을 같은 GLB에 묶어 재사용할 수 있습니다.</p></section>
<footer>제작: MediaPipe Pose Landmarker Heavy → 로컬 필터링 → Blender 4.5.3 보정·베이크 → Godot 4.7.2. 새 Scenario/Tripo 요청 없음. <a href="https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python" target="_blank" rel="noreferrer">MediaPipe 공식 문서</a> · <a href="https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf" target="_blank" rel="noreferrer">모델 카드</a></footer></main>
<script>
const byId=id=>document.getElementById(id);let internalSeek=false;
function status(id,msg){byId(id+'-status').textContent=msg}
document.querySelectorAll('[data-single]').forEach(b=>b.onclick=async()=>{const v=byId(b.dataset.single);v.currentTime=0;try{await v.play()}catch(e){status(v.id,'재생 실패: '+e.message)}});
for(const name of ['seedance2','pixverse6','kling3']){const a=byId(name+'-source'),b=byId(name+'-result'),out=byId(name+'-status');
document.querySelector('[data-pair="'+name+'"]').onclick=async()=>{internalSeek=true;a.currentTime=0;b.currentTime=0;internalSeek=false;try{await Promise.all([a.play(),b.play()]);out.textContent='함께 재생 중'}catch(e){out.textContent='재생 실패: '+e.message}};
document.querySelector('[data-stop="'+name+'"]').onclick=()=>{a.pause();b.pause();out.textContent='정지 · '+a.currentTime.toFixed(2)+'초'};
for(const v of [a,b]){const other=v===a?b:a;v.addEventListener('seeking',()=>{if(!internalSeek&&Math.abs(other.currentTime-v.currentTime)>.15){internalSeek=true;other.currentTime=Math.min(v.currentTime,4.999);internalSeek=false}});v.addEventListener('error',()=>out.textContent='영상 파일을 확인해 주세요');}
a.addEventListener('timeupdate',()=>{out.textContent=a.currentTime.toFixed(2)+' / 5.00초';if(!a.paused&&!b.paused&&Math.abs(a.currentTime-b.currentTime)>.12){internalSeek=true;b.currentTime=Math.min(a.currentTime,4.999);internalSeek=false}});
a.addEventListener('ended',()=>{b.pause();out.textContent='5.00초 · 재생 완료'});}
for(const v of document.querySelectorAll('video')){v.addEventListener('loadedmetadata',()=>{const id=v.id.endsWith('-source')?v.id.replace('-source',''):v.id;const o=byId(id+'-status');if(o)o.textContent=v.duration.toFixed(2)+'초 · 재생 준비됨'});if(v.id==='all-result'||v.id==='loop-result'){v.addEventListener('timeupdate',()=>status(v.id,v.currentTime.toFixed(2)+' / '+v.duration.toFixed(2)+'초'));v.addEventListener('error',()=>status(v.id,'영상 재생 오류'));}}
</script></html>'''
worst=max(v['max_joint_step_deg_60hz'] for v in godot['clips'].values())
surface=max(v['surface_floor_max_m'] for v in audit['clips'].values())*1.7*1000
qa=f'60Hz 관절 최대 변화 {worst:.2f}° / 프레임 · 루프 연결점 최대 {max(godot["clips"][name+"_loop"]["endpoint_rotation_gap_deg"] for name,_ in sources):.3f}° · 접지 표면 높이 최대 {surface:.2f}mm (게임 크기). 이 수치만으로 모든 발 미끄러짐·관통을 보장하지는 않습니다.'
page=page.replace('__CARDS__',''.join(cards)).replace('__ROWS__',''.join(rows)).replace('__QA__',qa)
(REVIEW/'video-animations.html').write_text(page,encoding='utf-8')
print('VIDEO_MOTION_REVIEW_READY',REVIEW/'video-animations.html',flush=True)
