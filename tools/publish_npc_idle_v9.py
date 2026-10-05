import json,struct,hashlib,shutil,zipfile
from pathlib import Path
import numpy as np
import httpx

R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v9'
V=R/'artifacts/production-lab-20261003/review/characters-idle-v9';V.mkdir(exist_ok=True)
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
 anim=g['animations'][0];anim['name']=reports[key]['clip'];anim['extras']={'loop':True,'duration_seconds':8,'character':key}
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
 assert max(gaps)<1e-5 and abs(max(last_times)-8)<1e-5
 for m in g['meshes']:
  for primitive in m['primitives']:
   a=primitive['attributes'];assert all(n in a for n in ['POSITION','TEXCOORD_0','JOINTS_0','WEIGHTS_0'])
   weights=accessor(g,binary,a['WEIGHTS_0']);assert np.abs(weights.sum(axis=1)-1).max()<.0001
 assert all('bufferView' in image for image in g['images'])
 encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
 p.write_bytes(struct.pack('<III',0x46546C67,2,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),0x4E4F534A)+encoded+tail)
 assert hashlib.sha256((R/'art/characters/npc_cast_closed_v2'/key/(key+'_static.glb')).read_bytes()).hexdigest()==reports[key]['source_sha256']
 reports[key]['individual_finger_rig']=True
 reports[key]['export_audit']={'skins':1,'animation_name':anim['name'],'channels':len(anim['channels']),'duration_seconds':max(last_times),'loop_channel_gap_max':max(gaps),'weights_normalized':True,'uv_and_embedded_textures':True}
 reports[key]['visual_review']='Actual skinned front renders at frames 1 and 61 and individual three-quarter standing renders checked; eight-second preview rendered. No gross mesh tearing visible. Hand closeups checked for the resting curl. Larger poses and locomotion are outside this idle validation.'
 (O/key/'verification.json').write_text(json.dumps(reports[key],indent=2))
 D=V/key;D.mkdir(exist_ok=True)
 for f in [key+'_rigged_idle.blend',key+'_rigged_idle.glb','verification.json','standing-angle.png','hand-detail.png','arm-detail.png']:shutil.copy2(O/key/f,D/f)
(O/'verification.json').write_text(json.dumps(reports,indent=2));shutil.copy2(O/'verification.json',V/'verification.json')
for f in ['npc-idle-preview.mp4','frame_1.png','frame_61.png','frame_121.png','frame_181.png','npc_rigged_idle_lineup_v9.blend']:shutil.copy2(O/f,V/f)
readme='''NPC body rigs and idle animations v9

Four individually skinned characters; Generic humanoid body skeleton plus fitted two-joint digit chains.
Source geometry, UV and textures preserved. Temporary welded mesh used only for binding.
Closed mouth kept unchanged. No facial rig or blink; digit chains follow the existing generated geometry.

Sora: Idle_Sora_SourceArms — a small arm reach, look down toward tunic, settle.
Moru: Idle_Moru_SourceArms — a modest one-hand gesture, then open shoulders.
Naru: Idle_Naru_SourceArms — lean and tilt to inspect each side while arms stay quiet.
Haeru: Idle_Haeru_SourceArms — slowly release one shoulder, glance aside, nod once.

Each character has an independent pose sequence with different holds and pauses.
There is no shared side-to-side sway cycle. Only low-amplitude breathing remains.

Source arm silhouette retained at rest; finger curl retained.
Ankle separation reduced from 0.206 times height to 0.166 times height (about 19%).
Pelvis lowered 0.006 times height, enabling soft knee flexion while keeping soles grounded.
Feet are turned out by 4 degrees. These are rig poses, not edits to the source mesh or UV.

V9 retains the source elbow/wrist relationship and lowers the entire arm 12 degrees as a rigid chain at the shoulder. Arm joints fitted to source mesh cross-sections. No arm IK or wrist world-space override. Small FK arm gestures of 3 and 5 degrees only for Sora and Moru. Existing digit rigs and planted feet retained. Merged source fingers are not rebuilt.

Each clip is 8 seconds at 30 fps, with a matching end key at frame 241.
Blender playback range is 1–240 to avoid repeating the endpoint. Press Space to play.
GLB contains one named skeletal animation per character; enable looping in your engine.
The loop flag in extras is descriptive metadata, not a universal runtime switch.
Use the generic skeleton or map bones explicitly for engine Humanoid retargeting.
Feet stay planted in these idle clips. Walking and large poses have not been validated.

The lineup Blender file contains all four separate rigs and actions with packed textures.
Preview, source and exported GLB animation are 30 fps.
See verification.json for all-frame deformation and GLB export checks.
No new API calls or Tripo credits were used.
'''
(O/'README.txt').write_text(readme,encoding='utf-8');shutil.copy2(O/'README.txt',V/'README.txt')
zip_path=R/'output/npc-rigged-idle-v9-20261005.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for f in ['README.txt','verification.json','npc_rigged_idle_lineup_v9.blend','npc-idle-preview.mp4']:z.write(O/f,f)
 for key in names:
  for f in [key+'_rigged_idle.blend',key+'_rigged_idle.glb','verification.json','standing-angle.png','hand-detail.png','arm-detail.png']:z.write(O/key/f,key+'/'+f)
shutil.copy2(zip_path,V/'all-rigged-models.zip')
cards=''.join(f'<article><h2>{names[k]}</h2><img src="{k}/standing-angle.png" loading="lazy" alt="{names[k]} 기본 서 있는 자세"><p>{descriptions[k]}</p><a href="{k}/hand-detail.png">손 확대 보기</a> · <a href="{k}/arm-detail.png">팔 관절 확대 보기</a><p><code>{reports[k]["clip"]}</code> · 8초 반복</p><a href="{k}/{k}_rigged_idle.blend">Blender</a> · <a href="{k}/{k}_rigged_idle.glb">애니메이션 GLB</a></article>' for k in names)
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NPC 몸 리깅·idle</title><style>body{font:17px/1.7 system-ui;background:#17212c;color:#edf3fb;max-width:1200px;margin:32px auto;padding:0 22px}a{color:#a8d4ff}video,img{width:100%;border-radius:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:#253340;padding:18px;border-radius:12px}code{font-size:14px}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style><h1>NPC 4명 · 팔 관절 변형 수정</h1><p>원본의 팔꿈치·손목 윤곽을 유지하고 팔 전체를 어깨에서 12도 내렸습니다. 팔 본을 실제 메쉬 단면에 맞춰 조정하고, 팔을 강제로 내리는 IK와 손목 방향 덮어쓰기를 제거했습니다. 소라와 모루는 작은 팔 제스처를 사용하며, 나루와 해루는 상체·머리 중심의 idle을 유지합니다. 손가락 리깅과 발 고정도 유지했습니다. 무릎은 살짝 굽히고 발은 조금 바깥으로 향하게 했습니다. 캐릭터별 idle 동작과 원본 얼굴·UV·텍스처를 유지했습니다. 페이스 리그·깜빡임은 포함하지 않습니다.</p><video src="npc-idle-preview.mp4" poster="frame_1.png" controls autoplay loop muted playsinline></video><p>8초 반복 · 원본/GLB/미리보기 30fps</p><p><a href="npc_rigged_idle_lineup_v9.blend">4명 통합 Blender 열기</a> · <a href="all-rigged-models.zip">전체 ZIP</a> · <a href="verification.json">검증 기록</a></p><div class="grid">'''+cards+'''</div><p>Blender에서 Space로 재생하세요. 각 파일에는 해당 NPC의 독립된 idle 클립이 들어 있습니다. 게임에서는 Generic 리그로 사용하거나 본을 매핑하고, 클립 반복을 켜주세요. 걷기와 큰 자세 변화는 아직 검증하지 않았습니다. 추가 Tripo 크레딧: 0.</p><p><a href="../characters-closed-mouth-v2/">원본 정적 모델</a></p></html>''',encoding='utf-8')
old=V.parent/'characters-closed-mouth-v2/index.html';html=old.read_text(encoding='utf-8');link='<p><a href="../characters-idle-v9/">새 버전: 몸 리깅·개별 idle 애니메이션 보기</a></p>'
if 'characters-idle-v9' not in html:old.write_text(html.replace('<div class="grid">',link+'<div class="grid">'),encoding='utf-8')
with httpx.Client(timeout=20) as client:assert client.get('http://127.0.0.1:8842/characters-idle-v9/').status_code==200
print('NPC_IDLE_PUBLISHED',str(zip_path),zip_path.stat().st_size)



