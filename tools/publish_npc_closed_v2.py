import json,shutil,struct,zipfile,httpx
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/npc_cast_closed_v2';REF=R/'art/references/npc_cast_closed_v2';V=R/'artifacts/production-lab-20261003/review/characters-closed-mouth-v2';V.mkdir(exist_ok=True);names={'sora':'소라','moru':'모루','naru':'나루','haeru':'해루'};items=[];cards=[]
for k,n in names.items():
 O=A/k;result=json.loads((O/'result.json').read_text(encoding='utf-8'));report=json.loads((O/'inspection.json').read_text(encoding='utf-8'));assert result['status']=='success'
 b=(O/(k+'_static.glb')).read_bytes();size,_=struct.unpack_from('<II',b,12);g=json.loads(b[20:20+size]);assert not g.get('skins') and not g.get('animations');assert all('TEXCOORD_0' in p['attributes'] for m in g['meshes'] for p in m['primitives']);assert all('bufferView' in im for im in g.get('images',[]))
 report.update(status='static_asset_verified',visual_review='Front, angle, back and face reviewed; closed mouth visible. Fine fingers and generated texture detail may need later polish.',face_rig=False,body_rig=False,glb_uv_and_embedded_textures_verified=True);(O/'inspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 D=V/k;D.mkdir(exist_ok=True)
 for f in ['front.png','angle.png','back.png','face.png',k+'_static.blend',k+'_static.glb','inspection.json']:shutil.copy2(O/f,D/f)
 shutil.copy2(REF/k/'03_body-turnaround.png',D/'reference.png');shutil.copy2(REF/k/'image-generation.json',D/'image-generation.json')
 item={'id':k,'name':n,'triangles':report['triangles'],'height_m':report['height_m'],'credits':result['credits_consumed'],'blend':str(O/(k+'_static.blend')),'glb':str(O/(k+'_static.glb'))};items.append(item)
 cards.append(f'''<article><h2>{n}</h2><img src="{k}/front.png"><p>{report['triangles']:,} 삼각형 · 입을 다문 정적 모델</p><p><a href="{k}/{k}_static.blend">Blender</a> · <a href="{k}/{k}_static.glb">GLB</a> · <a href="{k}/reference.png">닫힌 입 참고 이미지</a></p><details><summary>사선·후면·얼굴 확대</summary><img src="{k}/angle.png"><img src="{k}/back.png"><img src="{k}/face.png"></details></article>''')
 readme='''# 입을 다문 신규 캐릭터 4명 · 정적 모델

소라 / 모루 / 나루 / 해루. 제공된 v4 자료에서 내장 image_gen으로 입을 다문 참고 시트를 만든 뒤, 정면·우측·후면을 Tripo P2에 제공했습니다. 각 캐릭터의 얼굴·헤어·의상은 하나의 전신 생성 모델에 포함됩니다. 추가 리토폴로지나 얼굴 스컬프 수정은 하지 않았습니다.

정적 A포즈 모델입니다. 페이스 리그, 몸 리그, 표정 또는 걷기 애니메이션은 포함하지 않습니다. 몸 리깅과 게임 동작은 다음 단계입니다. UV/PBR 텍스처는 GLB에 포함되며, Blender 파일에는 확인용 카메라·조명이 추가되어 있습니다. GLB에는 캐릭터만 내보냈습니다.

초기 입 벌린 요청 2개는 각110크레딧 사용 후 사용자 요청 변경으로 사용하지 않습니다. 입 다문 신규4명은 각각110크레딧, 합계440. 이 작업 전체 Tripo사용660크레딧. 기존 승인한도 잔여20크레딧이며, 재생성은 자동으로 하지 않습니다.

기존 캐릭터 v13은 변경하지 않았습니다. 원본 자료, Tripo 원본 출력, 생성 이미지와 편집 요약은 각각 별도로 보존했습니다. 생성된 손가락 및 텍스처 세부는 추후 다듬을 수 있습니다.
''';(A/'README.md').write_text(readme,encoding='utf-8');shutil.copy2(A/'README.md',V/'README.md')
Z=R/'output/npc-closed-mouth-static-v2-20261005.zip'
with zipfile.ZipFile(Z,'w',zipfile.ZIP_DEFLATED) as z:
 z.write(A/'README.md','README.md')
 for k in names:
  for f in [k+'_static.blend',k+'_static.glb','inspection.json']:z.write(A/k/f,k+'/'+f)
  z.write(REF/k/'03_body-turnaround.png',k+'/closed-mouth-reference.png');z.write(REF/k/'image-generation.json',k+'/image-generation.json')
shutil.copy2(Z,V/'all-models.zip')
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>입을 다문 캐릭터 4명</title><style>body{font:17px/1.65 system-ui;background:#192631;color:#edf3fb;max-width:1200px;margin:32px auto;padding:0 22px}a{color:#b0d6ff}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:24px}article{background:#253340;padding:20px;border-radius:14px}img{width:100%;border-radius:10px}details img{margin-top:14px}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style><h1>입을 다문 신규 캐릭터 4명</h1><p>닫힌 입 참고 이미지를 먼저 생성하고 전신 통합 모델을 만들었습니다. 페이스 리깅은 보류했습니다. 현재는 몸 리그도 없는 정적 A포즈 모델입니다.</p><p><a href="all-models.zip">4명 Blender·GLB·참고 이미지 전체 다운로드</a> · <a href="../character-mesh-reset-v13/">보존한 기존 캐릭터</a> · <a href="README.md">제작·비용 기록</a></p><div class="grid">'''+''.join(cards)+'''</div></html>''',encoding='utf-8')
state={'state':'Closed_mouth_static_NPC_cast_v2','characters':items,'existing_character':'v13 unchanged','face_rig':False,'body_rig':False,'credits_closed_cast':440,'credits_obsolete_open_tasks':220,'approved_budget_remaining':20,'review_url':'http://127.0.0.1:8842/characters-closed-mouth-v2/','archive':str(Z)};(A/'workflow-status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=json.loads(p.read_text(encoding='utf-8-sig'));d['latest_static_npc_cast']=state;p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
with httpx.Client(timeout=20) as c:
 assert c.get(state['review_url']).status_code==200
 for k in names:assert c.head(state['review_url']+k+'/'+k+'_static.glb').status_code==200
print('NPC_CAST_PUBLISHED',state['review_url'],Z.stat().st_size)
