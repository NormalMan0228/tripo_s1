"""Publish a private local review of the generated body, never approve it."""
import hashlib
import html
import json
import shutil
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CHAR=ROOT/'art/characters/explorer_b_fullbody_v2'
OUT=CHAR/'03_generated'
REVIEW=ROOT/'artifacts/production-lab-20261003/review/character-fullbody-v2'
REVIEW.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
result=read(OUT/'generation-result.json')
inspect=read(OUT/'mesh-inspection.json')
blob=(OUT/'model.glb').read_bytes()
assert hashlib.sha256(blob).hexdigest()==result['sha256'],'original_glb_changed'
magic,version,total=struct.unpack_from('<4sII',blob)
assert magic==b'glTF' and version==2 and total==len(blob),'invalid_glb'
length,tag=struct.unpack_from('<I4s',blob,12)
assert tag==b'JSON','invalid_glb_chunk'
doc=json.loads(blob[20:20+length])
assert not doc.get('skins') and not doc.get('animations'),'unexpected_rig_or_animation'
assert not any('uri' in x for x in doc.get('buffers',[])+doc.get('images',[])),'external_glb_data'
assert (OUT/'review.blend').is_file(),'review_blend_missing'
required=['preview-front.png','preview-angle.png','preview-side.png','preview-back.png','preview-clay.png']
required += ['detail-'+region+'-'+mode+'.png' for region in ('face','hand-positive-y','hand-negative-y','feet') for mode in ('material','clay')]
for file in required:
    assert (OUT/file).stat().st_size>1000,'preview_missing_'+file
for file in required+['model.glb','review.blend','mesh-inspection.json','generation-request.json','generation-result.json']:
    shutil.copy2(OUT/file,REVIEW/file)
for name in ('front','back'):
    shutil.copy2(ROOT/f'art/references/explorer_b_fullbody_v2/{name}.png',REVIEW/f'reference-{name}.png')
notes=read(OUT/'quality-review.json') if (OUT/'quality-review.json').exists() else {'findings':[],'state':'visual_review_pending'}
e=html.escape
findings=''.join(f'<li><b>{e(x["region"])}</b> · {e(x["observation"])}<br><span>{e(x["recommendation"])}</span></li>' for x in notes['findings'])
gallery=''.join(f'<figure><a href="{name}" target="_blank"><img loading="lazy" src="{name}" alt="{label}"></a><figcaption>{label}</figcaption></figure>' for name,label in zip(required,[
 '실제 메시 · 정면','실제 메시 · 사선','실제 메시 · 측면','실제 메시 · 후면','실제 형상 · 회색 재질',
 '얼굴 · 재질','얼굴 · 형상','한쪽 손 · 재질','한쪽 손 · 형상','반대쪽 손 · 재질','반대쪽 손 · 형상','발 · 재질','발 · 형상']))
textures=', '.join(str(x['size'][0])+'×'+str(x['size'][1]) for x in inspect['textures'])
page=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>B형 탐험가 · 전신 메시 v2 검토</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f5ee;color:#283d36;font:16px/1.8 'Segoe UI','Malgun Gothic',sans-serif}}main{{max-width:1180px;margin:auto;padding:35px 24px 80px}}h1{{font-size:35px;line-height:1.3}}h2{{margin-top:35px}}a{{color:#225c4a}}.notice{{background:#fff0ce;border-left:4px solid #b38730;padding:18px 22px}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}figure{{margin:0;background:white;border:1px solid #dbe3d9;border-radius:12px;overflow:hidden}}img{{width:100%;display:block}}figcaption{{padding:10px 16px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:12px;border:1px solid #dce3d7;text-align:left}}nav{{display:flex;gap:18px;flex-wrap:wrap;margin:20px 0}}li{{margin:14px 0}}li span{{color:#626f64}}small{{color:#6b756e}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}h1{{font-size:28px}}}}
</style></head><body><main><small>2026-10-04 · 개발용 원본 · 3D 생성 검토 단계</small><h1>B형 탐험가<br>전신 베이스 메시 v2</h1><p class="notice"><b>머리·몸·손·발을 포함한 전신 생성 결과입니다.</b> 리깅·교체 부위의 조립·의복 교체·최종 UV·베이킹·애니메이션은 아직 수행하지 않았습니다. 머리카락과 겉옷은 후속 별도 자산입니다. 흰 속옷 아래 독립 피부 메시가 있다는 의미도 아닙니다.</p>
<nav><a href="#mesh">메시 전체</a><a href="#findings">검토 결과</a><a href="#spec">설정과 비용</a><a href="#source">원본 참조</a><a download href="review.blend">Blender 검토본</a><a download href="model.glb">생성 원본 GLB</a></nav>
<section id="mesh"><h2>전체와 근접 검토</h2><p>생성된 원본을 Blender에서 직접 렌더했습니다. 회색 화면은 텍스처를 끄고 같은 형상을 보여줍니다. 이미지를 누르면 개별 원본 크기로 볼 수 있습니다.</p><div class="grid">{gallery}</div></section>
<section id="findings"><h2>수정·교체 판단</h2><ul>{findings}</ul><p>최종 판단은 사용자 검토 후 진행합니다. 신체 전체를 다시 나누기보다 문제가 확인된 부위에만 수정·교체를 적용합니다. 정적 형상만으로 관절 변형이나 표정 품질을 검증했다고 보지 않습니다.</p></section>
<section id="spec"><h2>모델과 실측 비용</h2><table><tr><th>Tripo 모델</th><td>H3.1 · v3.1-20260211 · geometry_quality=detailed (Ultra)</td></tr><tr><th>입력</th><td>승인된 정면 + 후면, multiview-to-model</td></tr><tr><th>원본 설정</th><td>face_limit=1,000,000 / smart_low_poly=false / quad=false / generate_parts=false</td></tr><tr><th>메시 실측</th><td>{inspect['vertices']:,} vertices / {inspect['triangles']:,} triangles / {len(inspect['mesh_objects'])} mesh objects</td></tr><tr><th>텍스처</th><td>PBR · detailed · v3.0-20250812 · UV 포함 · {textures}</td></tr><tr><th>실제 생성 비용</th><td>{result['credits_consumed']} Tripo 크레딧 · 잔액 변화 {result['balance_delta']}</td></tr><tr><th>추가 사용</th><td>리깅 0 / 애니메이션 0 / Scenario 0</td></tr></table><p>고해상도 메시를 직접 게임에 넣은 결과가 아닙니다. 후속 수정·리토폴로지·베이킹의 원본으로 검토합니다. <a href="generation-request.json">요청 설정</a> · <a href="generation-result.json">실측 기록</a> · <a href="mesh-inspection.json">메시 구조 검사</a></p><p><a href="https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard">공식 API 설정</a> · <a href="https://developers.tripo3d.ai/en/models/v3-1">공식 요금표</a></p></section>
<section id="source"><h2>승인된 전신 참조</h2><div class="grid"><figure><img src="reference-front.png" loading="lazy" alt="전신 정면 참조"><figcaption>승인된 정면 이미지</figcaption></figure><figure><img src="reference-back.png" loading="lazy" alt="전신 후면 참조"><figcaption>승인된 후면 이미지</figcaption></figure></div></section></main></body></html>'''
(REVIEW/'index.html').write_text(page,encoding='utf-8')
summary={'state':'awaiting_user_3d_review','source_sha256_verified':True,'mesh_inspection':inspect,
 'actual_tripo_credits':result['credits_consumed'],'source_glb':str(OUT/'model.glb'),
 'review_blend':str(OUT/'review.blend'),'render_count':len(required),'replacements_made':False,'rigged':False,
 'notes':notes,'url':'http://127.0.0.1:8842/character-fullbody-v2/'}
(OUT/'review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('mesh_inspection','notes')},ensure_ascii=False))
