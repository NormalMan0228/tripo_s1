"""Package independent P2 sources and actual renders for the user's geometry gate."""
import hashlib
import html
import json
import shutil
import struct
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CHAR=ROOT/'art/characters/explorer_b_fullbody_v2'
OUT=CHAR/'04_replacement_parts_p2'
REVIEW=ROOT/'artifacts/production-lab-20261003/review/character-p2-parts'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
e=html.escape
REVIEW.mkdir(parents=True,exist_ok=True)
labels={'head':'머리','hand':'손','hair':'머리카락'}
all_parts={};sections=[];rows=[];heroes=[]
selection=read(ROOT/'art/references/explorer_b_modular_v1/final_images_selection.json')
view_labels={'front':'정면','angle':'사선','side':'측면','back':'후면','clay':'회색 형상'}
def figure(folder,file,label):
    width,height=struct.unpack('>II',(REVIEW/folder/file).read_bytes()[16:24])
    return f'<figure><a href="{folder}/{file}" target="_blank"><img width="{width}" height="{height}" loading="lazy" src="{folder}/{file}" alt="{e(label)}"></a><figcaption>{e(label)}</figcaption></figure>'
for part,label in labels.items():
    out=OUT/part;result=read(out/'generation-result.json');inspect=read(out/'mesh-inspection.json')
    request=read(out/'generation-request.json');quality=read(out/'quality-review.json')
    source=ROOT/result['file'];blob=source.read_bytes()
    assert request['model']=='P2-20260801' and request['quad'] and not request['texture']
    assert result['status']=='success' and hashlib.sha256(blob).hexdigest()==result['sha256']
    assert source.suffix=='.fbx' and blob.startswith(b'Kaydara FBX Binary')
    assert not inspect['rigged'] and not inspect['geometry_edited']
    quads=sum(o['polygon_sides'].get('4',0) for o in inspect['mesh_objects'])
    tris=sum(o['polygon_sides'].get('3',0) for o in inspect['mesh_objects'])
    assert quads>0
    entry={'state':'awaiting_user_geometry_review','model':'P2-20260801','source_mesh':source.relative_to(ROOT).as_posix(),
      'source_sha256':result['sha256'],'review_blend':(out/'review.blend').relative_to(ROOT).as_posix(),
      'quads':quads,'triangle_faces':tris,'render_triangles':inspect['triangles'],
      'requested_face_limit':request['face_limit'],'actual_tripo_credits':result['credits_consumed'],
      'reference_file':request['reference_file'],'reference_sha256':request['reference_sha256'],
      'rigged':False,'assembled':False,'fit_verified':False,'texture_generated':False,'quality':quality}
    all_parts[part]=entry
    target=REVIEW/part;target.mkdir(exist_ok=True)
    previews=['preview-'+v+'.png' for v in view_labels]+['wire-overview.png']
    for name in previews+['model.fbx','review.blend','generation-request.json','generation-result.json','mesh-inspection.json','topology-detail.json','quality-review.json']:
        assert (out/name).is_file(),'missing_'+part+'_'+name
        shutil.copy2(out/name,target/name)
    shutil.copy2(ROOT/request['reference_file'],target/'reference.png')
    heroes.append(figure(part,'preview-angle.png',label+' · 독립 P2 메시'))
    findings=''.join(f'<li><b>{e(x["region"])}</b> · {e(x["observation"])}<p class="sub">다음 조치: {e(x["recommendation"])}</p></li>' for x in quality['findings'])
    gallery=''.join(figure(part,'preview-'+v+'.png',label+' · '+l) for v,l in view_labels.items())
    gallery+=figure(part,'wire-overview.png',label+' · 실제 폴리곤 경계')
    sections.append(f'<section id="{part}"><h2>{label} · 별도 생성 결과</h2><p><a download href="{part}/model.fbx">원본 FBX</a> · <a download href="{part}/review.blend">Blender 검토본</a> · <a href="{part}/mesh-inspection.json">실측</a></p><ul>{findings}</ul><div class="grid">{gallery}</div><details><summary>사용한 승인 참조 이미지</summary>{figure(part,"reference.png",label+" · 승인 참조")}</details></section>')
    rows.append(f'<tr><th>{label}</th><td>{request["face_limit"]:,}</td><td>{quads:,}</td><td>{tris:,}</td><td>{inspect["triangles"]:,}</td><td>{result["credits_consumed"]:g}</td></tr>')
total=sum(x['actual_tripo_credits'] for x in all_parts.values())
manifest={'date':'2026-10-04','state':'awaiting_user_geometry_review','model':'P2-20260801','parts':all_parts,
 'actual_tripo_credits':total,'scenario_credits':0,'new_image_generation_calls':0,
 'source_reference_reuse':'previously user-approved individual head, hand and hair images',
 'assembly_performed':False,'rigging_performed':False,'texture_stage_performed':False,
 'future_generation_policy':{'scope':'developer_character_generation','default_model':'P2-20260801','fallback_to_H_series':False,
  'evidence':'2026-10-04 user: 앞으로 p2를 쓸 겁니다.'},
 'next_action':'User reviews independent head, hand and hair meshes before replacing, fitting or rigging.',
 'url':'http://127.0.0.1:8842/character-p2-parts/'}
save(OUT/'manifest.json',manifest);save(REVIEW/'manifest.json',manifest)
page=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P2 캐릭터 · 머리·손·헤어 검토</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f4ed;color:#2c3e36;font:16px/1.8 "Segoe UI","Malgun Gothic",sans-serif}}main{{max-width:1180px;margin:auto;padding:36px 24px 70px}}h1{{font-size:34px;line-height:1.4}}h2{{margin-top:36px}}a{{color:#236049}}.notice{{background:#fff0d0;border-left:5px solid #b58931;padding:18px 22px}}nav{{display:flex;gap:18px;flex-wrap:wrap;margin:25px 0}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}}.heroes{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}figure{{margin:0;border:1px solid #dce2d8;background:white;border-radius:12px;overflow:hidden}}img{{display:block;width:100%;height:auto}}figcaption{{padding:10px 14px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px;border:1px solid #dce2d8;text-align:left}}li{{margin:16px 0}}.sub,small{{color:#657166}}details{{margin:20px 0;padding:15px;background:#fff}}summary{{cursor:pointer}}section{{scroll-margin-top:18px}}.scroll{{overflow:auto}}@media(max-width:700px){{.grid,.heroes{{grid-template-columns:1fr}}h1{{font-size:28px}}}}
</style></head><body><main><small>2026-10-04 · 3D 부위 생성 · 형상 검토 대기</small><h1>Tripo P2<br>머리 · 손 · 머리카락</h1><p class="notice"><b>각각의 승인 참조로 새로 생성한 독립 쿼드 메시입니다.</b> 전신에서 잘라낸 부품이 아닙니다. 실제 총비용 {total:g}크레딧. 앞으로 개발용 캐릭터 생성은 P2를 기본으로 기록했습니다. 현재는 형상 검토 단계이며 텍스처·조립·리깅은 진행하지 않았습니다.</p>
<nav><a href="#head">머리</a><a href="#hand">손</a><a href="#hair">머리카락</a><a href="#spec">명세와 비용</a><a href="../character-fullbody-p2/">전신 베이스</a><a download href="P2_Replacement_Parts.zip">전체 파일 저장</a></nav><div class="heroes">{''.join(heroes)}</div>
{''.join(sections)}<section id="spec"><h2>명세 · 실제 비용</h2><p>모든 부품: P2-20260801 / image-to-model / quad=true / seed=20261004 / texture=false / pbr=false / export_uv=true. 자동 UV는 생성되었지만 최종 UV 검토 전입니다.</p><div class="scroll"><table><tr><th>부품</th><th>목표 면수</th><th>실제 쿼드</th><th>삼각형 면</th><th>삼각화 환산</th><th>Tripo 비용</th></tr>{''.join(rows)}</table></div><p>이 페이지의 부품 비용만 합산했습니다. 전신 P2 100크레딧과 앞선 H3.1 60크레딧은 별도 기존 사용분입니다. Scenario·리깅·애니메이션 추가 사용은 0입니다.</p><p class="notice">손은 한쪽 생성 원본입니다. 좌우 판별과 실제 손바닥/손등 확인 후 Blender에서 반대쪽을 미러로 만듭니다. 아직 두상 맞춤, 목/손목 접합, 색 통일, 신체 가중치, 얼굴/손 변형을 검증한 결과가 아닙니다. 검토 후 필요한 부분만 수정·교체합니다.</p><p><a href="manifest.json">재사용 자산 기록</a> · <a href="https://developers.tripo3d.ai/en/docs/generation-image-to-model/p">공식 P2 이미지 API</a></p></section></main></body></html>'''
(REVIEW/'index.html').write_text(page,encoding='utf-8')
with zipfile.ZipFile(REVIEW/'P2_Replacement_Parts.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for part in labels:
        for file in (REVIEW/part).iterdir():
            if file.is_file():archive.write(file,file.relative_to(REVIEW).as_posix())
    archive.write(REVIEW/'manifest.json','manifest.json');archive.write(REVIEW/'index.html','index.html')
plan=read(CHAR/'production-plan.json')
plan.update(state='p2_replacement_parts_awaiting_user_review',default_character_generation_model='P2-20260801',
    model_policy=manifest['future_generation_policy'],replacement_parts=all_parts,
    replacement_parts_credits=total,replacement_parts_manifest=(OUT/'manifest.json').relative_to(ROOT).as_posix(),
    next_action=manifest['next_action'])
save(CHAR/'production-plan.json',plan)
print(json.dumps({'state':manifest['state'],'credits':total,'parts':list(all_parts),'url':manifest['url']},ensure_ascii=False))
