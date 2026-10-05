"""Package seven HD source meshes with per-part views and measured cost."""
import hashlib
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/characters/explorer_b_hd_restart_v1'
REVIEW = ROOT/'artifacts/production-lab-20261003/review/character-hd-restart'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
save = lambda p,v: p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
manifest = read(BASE/'generation-manifest.json')
budget = read(ROOT/manifest['budget_file'])
REVIEW.mkdir(parents=True,exist_ok=True)
notes = {
 'fullbody':['전신·속옷·양손·양발이 포함된 생성 원본입니다.', '두피와 팔꿈치 주변에 가로 경계선이 보입니다. 실제 틈인지 표면 굴곡인지 Blender에서 검사할 대상입니다. 기존 손가락의 간격과 머리/손 교체 영역도 조립 전에 검토해야 합니다.'],
 'head':['눈썹·귀·입술 형상이 독립된 머리 원본에 생성됐습니다.', '홍채와 하이라이트가 돌출된 형상으로 해석되어 있습니다. 얼굴 리깅 전에 안구·눈꺼풀 구조와 함께 정리할 후보입니다.'],
 'hair':['갈라진 앞머리와 단발 실루엣을 가진 독립 머리카락입니다.', '머리에 맞춘 크기·두피 안쪽 간섭·모발 틈은 아직 검증하지 않았습니다.'],
 'hand':['엄지를 포함한 다섯 손가락과 손톱 형상이 보입니다.', '한쪽 손의 생성 원본입니다. 손바닥·손등, 좌우 판별 및 손목 연결은 다음 검토 대상입니다.'],
 'upper_clothing':['기존 자켓 디자인으로 상의 외피를 생성했습니다. 흰 안쪽 상의는 전신 기반에 포함되어 있습니다.', '카라·소매 끝·자켓 안쪽 두께와 신체 간격을 맞추는 작업은 이후 단계입니다.'],
 'lower_clothing':['주머니와 허리 디테일을 포함한 하의입니다.', '별도의 벨트 생성은 수행하지 않았습니다. 기존 벨트 디자인은 하의 그룹의 후속 조정 대상으로 남겨두었습니다.'],
 'footwear':['한쪽 부츠의 생성 원본입니다.', '반대쪽 미러 제작과 발 크기·발목 간격 검토는 이후 단계입니다.']
}
sections=[]
rows=[]
for part,entry in manifest['parts'].items():
    folder=BASE/part
    request=read(folder/'generation-request.json')
    result=read(folder/'generation-result.json')
    mesh=read(folder/'mesh-review.json')
    assert result['status']=='success'
    assert request['model']=='v3.1-20260211' and request['geometry_quality']=='detailed'
    assert not request['texture'] and not request['pbr'] and not request['smart_low_poly']
    assert result['sha256']==hashlib.sha256((folder/'model.glb').read_bytes()).hexdigest()==mesh['source_sha256']
    assert not mesh['geometry_edited'] and not mesh['rigged']
    target=REVIEW/part
    target.mkdir(exist_ok=True)
    for name in ['model.glb',f'{part}_HD.blend','mesh-review.json','generation-request.json','generation-result.json']:
        assert (folder/name).is_file()
        shutil.copy2(folder/name,target/name)
    for view in ['front','angle','side','back']:
        shutil.copy2(folder/f'preview-{view}.png',target/f'preview-{view}.png')
    for i,ref in enumerate(request['reference_files']):
        shutil.copy2(ROOT/ref,target/f'reference-{i+1}.png')
    label=entry['label']
    view_labels={'front':'정면','angle':'사선','side':'측면','back':'후면'}
    views=''.join(f'<figure><a href="{part}/preview-{view}.png" target="_blank"><img loading="lazy" src="{part}/preview-{view}.png" alt="{html.escape(label)} {text}"></a><figcaption>{text}</figcaption></figure>' for view,text in view_labels.items())
    references=''.join(f'<a href="{part}/reference-{i+1}.png" target="_blank">입력 이미지 {i+1}</a> ' for i in range(len(request['reference_files'])))
    findings=''.join(f'<li>{html.escape(note)}</li>' for note in notes[part])
    sections.append(f'<section id="{part}"><h2>{html.escape(label)}</h2><div class="meta">실제 {mesh["triangles"]:,} 삼각형 · {result["credits_consumed"]:g}크레딧 · HD 원본</div><p class="downloads"><a download href="{part}/model.glb">원본 GLB</a><a download href="{part}/{part}_HD.blend">Blender 파일</a></p><ul>{findings}</ul><div class="views">{views}</div><details><summary>입력 이미지와 생성 명세</summary><p>{references}</p><a href="{part}/generation-request.json">가린 요청 명세</a> · <a href="{part}/generation-result.json">작업 결과·비용</a> · <a href="{part}/mesh-review.json">메쉬 실측</a></details></section>')
    rows.append(f'<tr><th><a href="#{part}">{html.escape(label)}</a></th><td>{request["face_limit"]:,}</td><td>{mesh["triangles"]:,}</td><td>{result["credits_consumed"]:g}</td></tr>')
    entry.update(review_blend=str((folder/f'{part}_HD.blend').relative_to(ROOT)),
                 measured_vertices=mesh['vertices'],measured_triangles=mesh['triangles'],
                 geometry_review='awaiting_user',review_notes=notes[part])

total=sum(float(e['credits_consumed']) for e in manifest['parts'].values())
assert total<=budget['tripo_cap']
manifest.update(state='seven_HD_sources_awaiting_user_geometry_review',actual_credits=total,
                authorized_remaining=budget['tripo_cap']-total,new_image_generation_calls=0,
                scenario_credits=0,automatic_resubmit=False,
                review_url='http://127.0.0.1:8842/character-hd-restart/',
                next_action='User reviews geometry before texture, fitting, topology or rigging work.')
save(BASE/'generation-manifest.json',manifest)
save(REVIEW/'generation-manifest.json',manifest)
nav=''.join(f'<a href="#{part}">{html.escape(e["label"])}</a>' for part,e in manifest['parts'].items())
page=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>캐릭터 HD · 7개 파츠 검토</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f3f4;color:#26363d;font-family:system-ui,"Malgun Gothic",sans-serif;line-height:1.65}}main{{max-width:1400px;margin:auto;padding:32px 24px 80px}}h1{{font-size:34px;margin:0 0 12px}}h2{{font-size:27px;margin:0 0 8px}}p{{margin:8px 0 16px}}a{{color:#17506b}}header,section{{background:white;padding:28px;border-radius:18px;margin:22px 0;border:1px solid #dce3e6}}nav{{position:sticky;top:0;padding:12px;background:#ffffffed;backdrop-filter:blur(10px);display:flex;gap:12px;flex-wrap:wrap;z-index:2;border-bottom:1px solid #dae1e5}}nav a{{text-decoration:none;padding:5px 12px;border-radius:9px;background:#eaf0f3}}section{{scroll-margin-top:110px}}.tag{{font-weight:700;color:#3e6f76;letter-spacing:.07em}}.cost{{display:flex;gap:20px;flex-wrap:wrap;margin:20px 0}}.cost b{{font-size:24px;display:block}}.cost>div{{padding:14px 20px;background:#edf3f4;border-radius:12px;min-width:160px}}.views{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}figure{{margin:0}}img{{width:100%;display:block;border-radius:12px;background:#999;aspect-ratio:1/1;object-fit:contain}}figcaption{{text-align:center;padding:6px;font-weight:600}}#fullbody img{{aspect-ratio:5/7}}.meta{{color:#527078}}.downloads{{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}}.downloads a{{padding:8px 15px;border:1px solid #c3d4db;border-radius:9px;text-decoration:none}}details{{margin-top:20px;background:#f5f7f8;padding:14px;border-radius:10px}}summary{{cursor:pointer}}table{{border-collapse:collapse;width:100%;margin-top:18px}}th,td{{border-bottom:1px solid #dfe5e8;text-align:left;padding:10px}}.scroll{{overflow:auto}}li{{margin:5px 0}}.note{{border-left:4px solid #a1b9c4;padding:12px 18px;background:#f4f7f8}}@media(max-width:700px){{main{{padding:14px}}header,section{{padding:20px}}.views{{grid-template-columns:1fr}}h1{{font-size:27px}}}}
</style></head><body><main><header><div class="tag">기존 디자인 유지 · HD 메쉬 생성 단계</div><h1>캐릭터 HD · 7개 파츠</h1><p>Tripo H3.1 <b>v3.1-20260211</b> · <b>geometry_quality=detailed (Ultra)</b><br>승인된 기존 이미지로 새로 생성한 실제 메쉬입니다. 각 파츠의 정면·사선·측면·후면을 개별로 확인할 수 있습니다.</p><div class="cost"><div>실제 사용<b>{total:g}크레딧</b></div><div>추가 승인 한도<b>{budget['tripo_cap']:g}크레딧</b></div><div>이 한도의 잔여<b>{budget['tripo_cap']-total:g}크레딧</b></div></div><p class="note">현재는 무채색 형상 검토 단계입니다. UV·텍스처·조립·리깅으로 진행하기 전에 확인해주세요. 이전 캐릭터·맵 예산과 원본 파일은 보존했습니다. 손과 신발은 한쪽 생성 원본이며, 반대쪽 제작과 몸에 맞추기는 이후 단계입니다.</p><div class="scroll"><table><tr><th>파츠</th><th>요청 상한</th><th>실제 삼각형</th><th>사용 크레딧</th></tr>{''.join(rows)}</table></div><p><a href="generation-manifest.json">전체 생성 기록</a> · <a href="https://developers.tripo3d.ai/en/models/v3-1">공식 모델·비용</a></p></header><nav>{nav}</nav>{''.join(sections)}</main></body></html>'''
(REVIEW/'index.html').write_text(page,encoding='utf-8')
policy_path=ROOT/'docs/CHARACTER_GENERATION_POLICY.json'
policy=read(policy_path)
policy.update(default_geometry_model='v3.1-20260211',api_model_version_status='verified_HD_H3_1',
              current_geometry_outputs=str((BASE/'generation-manifest.json').relative_to(ROOT)),
              current_stage='seven_HD_sources_awaiting_user_geometry_review',new_HD_generation_submitted=True,
              current_batch_credit_cap=1000,current_batch_actual_credits=total)
policy['part_plan']['upper_and_lower_group_reference_preparation_pending']=False
save(policy_path,policy)
print(json.dumps({'parts':7,'model':'v3.1-20260211','actual_credits':total,
                  'remaining_authorized':budget['tripo_cap']-total,'url':manifest['review_url']},ensure_ascii=False))
