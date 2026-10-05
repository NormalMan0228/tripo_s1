import json,struct,hashlib,shutil,zipfile
from pathlib import Path
import numpy as np
import httpx

R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11'
V=R/'artifacts/production-lab-20261003/review/characters-idle-v11';V.mkdir(exist_ok=True)
names={'sora':'소라','moru':'모루','naru':'나루','haeru':'해루'}
descriptions={'sora':'옷매무새를 내려다보며 한 팔을 조금 움직이기','moru':'한 손으로 작은 제스처 후 어깨 펴기','naru':'앞으로 기울여 좌우를 호기심 있게 살피기','haeru':'한쪽 어깨 풀기 후 느긋한 끄덕임'}
reports=json.loads((O/'verification.json').read_text())
def accessor(g,b,index):
 a=g['accessors'][index];v=g['bufferViews'][a['bufferView']]
 components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
 dt={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
 width=np.dtype(dt).itemsize*components;stride=v.get('byteStride',width)
 arr=np.ndarray((a['count'],components),dtype=dt,buffer=b,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(stride,np.dtype(dt).itemsize)).copy()
 if a.get('normalized'):arr=arr/np.iinfo(dt).max
 return arr
for key in names:
 p=O/key/(key+'_rigged_idle.glb');raw=p.read_bytes();jlen=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+jlen]);tail=raw[20+jlen:];binary=bytearray(tail[8:])
 assert len(g.get('skins',[]))==1 and len(g.get('animations',[]))==1
 anim=g['animations'][0];anim['name']=reports[key]['clip'];anim['extras']={'loop':True,'duration_seconds':20,'character':key}
 # Blender frame 1 exports at 1/30 s. Move only time accessors to a zero origin.
 inputs=set(s['input'] for s in anim['samplers']);origin=min(float(accessor(g,binary,i)[0,0]) for i in inputs)
 for i in inputs:
  a=g['accessors'][i];v=g['bufferViews'][a['bufferView']];assert a['componentType']==5126 and a['type']=='SCALAR'
  times=np.ndarray((a['count'],),dtype='<f4',buffer=binary,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',4),));times-=origin
 tail=tail[:8]+bytes(binary)
 gaps=[];last_times=[]
 for c in anim['channels']:
  sampler=anim['samplers'][c['sampler']];times=accessor(g,binary,sampler['input']);values=accessor(g,binary,sampler['output'])
  assert np.isfinite(values).all();last_times.append(float(times[-1,0]));assert abs(times[0,0])<1e-5
  gap=float(np.linalg.norm(values[-1]-values[0]))
  if c['target']['path']=='rotation':gap=min(gap,float(np.linalg.norm(values[-1]+values[0])))
  gaps.append(gap)
 assert max(gaps)<1e-5 and abs(max(last_times)-20)<1e-5
 for m in g['meshes']:
  for primitive in m['primitives']:
   a=primitive['attributes'];assert all(n in a for n in ['POSITION','TEXCOORD_0','JOINTS_0','WEIGHTS_0'])
   weights=accessor(g,binary,a['WEIGHTS_0']);assert np.abs(weights.sum(axis=1)-1).max()<.0001
 assert all('bufferView' in image for image in g['images'])
 encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
 p.write_bytes(struct.pack('<III',0x46546C67,2,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),0x4E4F534A)+encoded+tail)
 assert hashlib.sha256((R/'art/characters/npc_cast_closed_v2'/key/(key+'_static.glb')).read_bytes()).hexdigest()==reports[key]['source_sha256']
 reports[key]['individual_finger_rig']=True
 reports[key]['description']={'sora':'Right hand toward chin; thoughtful head tilt','moru':'Hands at trouser pockets; slow downward and sideways glances','naru':'Right hand on satchel strap; downward glance','haeru':'Arms folded with hands on opposite arms; slow head tilt'}[key]
 reports[key].pop('motion_amplitude_ratio_to_v3',None)
 reports[key]['audit'].pop('max_motion_m',None)
 reports[key]['export_audit']={'skins':1,'animation_name':anim['name'],'channels':len(anim['channels']),'duration_seconds':max(last_times),'loop_channel_gap_max':max(gaps),'weights_normalized':True,'uv_and_embedded_textures':True}
 reports[key]['audit'].pop('head_motion_m',None);reports[key]['audit'].pop('hand_motion_m',None)
 reports[key]['visual_review']='Reference contact sheet inspected; skinned poses checked at 0, 7, 13 and 16 seconds plus individual body and arm views. Animation authored manually from the reference, not motion capture.'
 (O/key/'verification.json').write_text(json.dumps(reports[key],indent=2))
 D=V/key;D.mkdir(exist_ok=True)
 for f in [key+'_rigged_idle.blend',key+'_rigged_idle.glb','verification.json','standing-angle.png','hand-detail.png','arm-detail.png','key-pose-front.png','pose-comparison.png']:shutil.copy2(O/key/f,D/f)
(O/'verification.json').write_text(json.dumps(reports,indent=2));shutil.copy2(O/'verification.json',V/'verification.json')
for f in ['npc-idle-preview.mp4','frame_1.png','frame_211.png','frame_391.png','frame_481.png','npc_rigged_idle_lineup_v11.blend']:shutil.copy2(O/f,V/f)
descriptions={'sora':'3–11초: 턱에 손을 가져가며 생각하기','moru':'주머니 입구에 손을 둔 자세 · 천천히 아래와 옆을 보기','naru':'10–19초: 가방 끈 쪽으로 손을 올리고 내려다보기','haeru':'팔짱 자세 · 13–20초: 고개를 기울였다 돌아오기'}
readme='''NPC reference poses and improved arm deformation v11
20-second independent clips, 30 fps, Blender playback frames 1–600.
Matching loop endpoint at frame 601. GLB key times normalized to 0–20 seconds.
Source: user-provided PixVerse/Seedance reference video, inspected at 0.5-second intervals.
This is manually authored skeletal animation from visual reference, not automatic motion capture.

Sora: right hand toward chin, thoughtful head tilt at 3–11 s.
Moru: hands at the pocket openings, downward and sideways glances.
Naru: right hand toward bag strap at 10–19 s, look down.
Haeru: folded arms, slow head tilt at 13–20 s.
The reference tail is adapted to return smoothly to the initial pose for game looping.

Forearm twist and elbow support bones added. Hand axis bend limited to 18 degrees at key poses and checked across all frames. Finger curls use the source finger planes.
Body, hand and digit rig animations only. No facial animation or blink.
Original mesh, textures and UV retained; v9 fitted arm joints and planted feet retained.
The source has no modeled pocket cavity: Moru fingertips are occluded behind the trouser surface while the wrists stay at the openings.
Generated coarse/merged fingers remain; this is not a rebuilt high-detail hand mesh.

Use the GLB named animation with looping enabled in the game engine.
Generic skeleton; explicit Humanoid bone mapping may be needed for retargeting.
All 601 frames checked for finite deformation, adjacent-frame continuity and planted feet.
Exported GLB checked for normalized weights, UV/embedded textures, 20 s duration and loop endpoint.
No new Tripo credits used. v9 originals preserved.
'''
(O/'README.txt').write_text(readme,encoding='utf-8');shutil.copy2(O/'README.txt',V/'README.txt')
shutil.copytree(O/'reference',V/'reference',dirs_exist_ok=True)
zip_path=R/'output/npc-reference-idle-v11-20261005.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for f in ['README.txt','verification.json','npc_rigged_idle_lineup_v11.blend','npc-idle-preview.mp4']:z.write(O/f,f)
 for key in names:
  for f in [key+'_rigged_idle.blend',key+'_rigged_idle.glb','verification.json','standing-angle.png','hand-detail.png','arm-detail.png','key-pose-front.png','pose-comparison.png']:z.write(O/key/f,key+'/'+f)
 z.write(O/'reference/npc-idle-reference.mp4','reference/npc-idle-reference.mp4')
shutil.copy2(zip_path,V/'all-rigged-models.zip')
cards=''.join(f'<article><h2>{names[k]}</h2><img src="{k}/pose-comparison.png" alt="{names[k]} 참고 영상과 수정 모델 비교"><p>{descriptions[k]}</p><p><code>{reports[k]["clip"]}</code></p><a href="{k}/{k}_rigged_idle.blend">Blender</a> · <a href="{k}/{k}_rigged_idle.glb">게임용 GLB</a> · <a href="{k}/arm-detail.png">팔 확대</a> · <a href="{k}/hand-detail.png">손 확대</a></article>' for k in names)
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>영상 기반 NPC idle</title><style>body{font:17px/1.7 system-ui;background:#17212c;color:#edf3fb;max-width:1200px;margin:32px auto;padding:0 22px}a{color:#a8d4ff}video,img{width:100%;border-radius:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:#253340;padding:18px;border-radius:12px}code{font-size:14px}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style><h1>영상 기반 NPC 4명 · 개별 idle</h1><p>영상의 턱에 손 올리기·주머니 자세·가방 끈 잡기·팔짱을 다시 맞춘 20초 반복 애니메이션입니다. 팔뚝 비틀림 본과 팔꿈치 보조 본을 추가하고, 손목은 팔뚝을 따라가도록 수정했습니다. 반복 끝은 첫 자세로 부드럽게 연결했습니다. 몸·손 리깅을 사용하며, 얼굴 표정과 깜빡임은 포함하지 않습니다.</p><video src="npc-idle-preview.mp4" poster="frame_1.png" controls autoplay loop muted playsinline></video><p>20초 반복 · 30fps · 발 고정</p><p><a href="npc_rigged_idle_lineup_v11.blend">4명 통합 Blender</a> · <a href="all-rigged-models.zip">전체 ZIP</a> · <a href="verification.json">검증 기록</a></p><div class="grid">'''+cards+'''</div><details><summary>참고 영상과 비교</summary><video src="reference/npc-idle-reference.mp4" controls muted playsinline></video><img src="reference/contact-sheet.png" alt="영상 동작 분석"></details><p>Blender에서 Space로 재생하세요. 게임에서는 해당 클립의 반복을 켜주세요. 모루는 실제 주머니 구멍이 없는 원본 모델의 바지 앞면 뒤로 손가락을 넣어 주머니 자세를 표현했습니다. 추가 Tripo 크레딧: 0.</p><a href="../characters-idle-v9/">이전 기본 자세</a></html>''',encoding='utf-8')
with httpx.Client(timeout=20) as client:assert client.get('http://127.0.0.1:8842/characters-idle-v11/').status_code==200
print('VIDEO_IDLE_PUBLISHED',zip_path,zip_path.stat().st_size)


