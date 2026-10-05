"""Save the actual P2 outputs and review page; retain user approval gates."""
import hashlib
import html
import json
import shutil
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CHAR=ROOT/'art/characters/explorer_b_fullbody_v2'
OUT=CHAR/'03_generated_p2'
HD=CHAR/'03_generated'
REVIEW=ROOT/'artifacts/production-lab-20261003/review/character-fullbody-p2'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
result=read(OUT/'generation-result.json');inspect=read(OUT/'mesh-inspection.json')
request=read(OUT/'generation-request.json');topology=read(OUT/'topology-detail.json')
source=ROOT/result['file'];blob=source.read_bytes()
assert hashlib.sha256(blob).hexdigest()==result['sha256'],'native_source_changed'
assert source.suffix=='.fbx' and blob.startswith(b'Kaydara FBX Binary'),'quad_native_fbx_missing'
assert request['model']=='P2-20260801' and request['quad'] is True and request['texture'] is False
quads=sum(x['polygon_sides'].get('4',0) for x in inspect['mesh_objects'])
triangles=sum(x['polygon_sides'].get('3',0) for x in inspect['mesh_objects'])
assert quads>0 and not inspect['rigged'] and not inspect['geometry_edited']
names=[('preview-'+view+'.png',label) for view,label in [
 ('front','全身 정면'),('angle','전신 사선'),('side','전신 측면'),('back','전신 후면'),('clay','회색 형상')]]
names += [('wire-'+region+'.png',label) for region,label in [
 ('fullbody','전신 · 실제 폴리곤 와이어'),('face','얼굴 · 실제 폴리곤 와이어'),
 ('hand-positive-y','한쪽 손 · 측면 와이어'),('hand-negative-y','반대쪽 손 · 측면 와이어')]]
names += [('detail-'+region+'-clay.png',label) for region,label in [
 ('face','얼굴 확대'),('hand-positive-y','한쪽 손 확대'),('hand-negative-y','반대쪽 손 확대'),('feet','발 확대')]]
for name,_ in names: assert (OUT/name).stat().st_size>1000,'missing_preview_'+name
notes={'state':'awaiting_user_geometry_review','findings':[
 {'region':'전신과 비율','observation':'머리·목·양팔·손·다리·발을 포함하는 전신 결과. 측면에서 몸과 발의 실루엣이 읽힌다. 몸은 약 1m 높이의 정규화 크기로, 게임의 실제 키는 아직 설정하지 않았다.',
  'recommendation':'승인된 정면·후면과 함께 전체 비율을 먼저 검토한다. 머리카락과 겉옷을 붙인 결과는 아니다.','evidence':['preview-front.png','preview-side.png','preview-back.png']},
 {'region':'연결 구조','observation':'Blender 객체는 1개지만 연결된 메시 섬은 7개다. 위치 범위상 머리/목, 양팔/손, 양다리/발, 상의, 하의에 대응한다. 열린 경계 486개와 세 면 이상이 공유하는 엣지 53개를 검사했다.',
  'recommendation':'열린 옷자락까지 무조건 병합하지 않는다. 신체 접합부와 비정상 연결을 구분해 후속 Blender 작업에서 확인한다. 속옷 아래 독립 피부가 존재한다고 가정하지 않는다.',
  'evidence':['topology-detail.json','mesh-inspection.json','wire-fullbody.png']},
 {'region':'얼굴','observation':'눈썹과 속눈썹은 실제 돌출 형상이다. 눈 주변의 가장자리와 입꼬리에 작은 핀칭이 남아 있다. 비정상 엣지 53개 중 좌표 구간 기준 52개가 머리 높이에 있다. 눈·눈꺼풀·입 내부의 기능은 검증하지 않았다.',
  'recommendation':'눈 주변 연결과 눈썹/속눈썹을 먼저 정리한다. 독립 안구, 눈꺼풀 루프, 입 내부를 준비한 후 얼굴 리깅을 진행한다. 전체 머리 교체가 필요한지는 사용자 검토 후 결정한다.',
  'evidence':['detail-face-clay.png','wire-face.png','topology-detail.json']},
 {'region':'양손','observation':'측면에서 손가락들의 분리가 보이지만 손끝이 각지고, 정면 각도에서는 여러 손가락이 겹쳐 보인다. 이 투영만으로 손가락 전체가 붙었다고 판정하지 않는다.',
  'recommendation':'각 손의 측면 와이어에서 손가락 사이와 손톱/손끝을 확인한다. 필요한 부분만 형상을 보정하거나 기존 독립 손 후보로 교체한 뒤 굽힘 테스트한다.',
  'evidence':['preview-side.png','wire-hand-positive-y.png','wire-hand-negative-y.png']},
 {'region':'발','observation':'양발의 다섯 발가락이 형상으로 읽힌다. 발 높이에 비정상 엣지가 1개 남아 있다.',
  'recommendation':'해당 엣지의 중복/연결을 수정하고 신발 안에 들어갈 실루엣을 검토한다.','evidence':['detail-feet-clay.png','topology-detail.json']}
 ],'rigging_validated':False,'uv_final_review':False,'texture_generated':False,'symmetry_final_review':False}
save(OUT/'quality-review.json',notes)
REVIEW.mkdir(parents=True,exist_ok=True)
files=[name for name,_ in names]+['model.fbx','review.blend','mesh-inspection.json','topology-detail.json','quality-review.json','generation-request.json','generation-result.json']
for name in files: shutil.copy2(OUT/name,REVIEW/name)
for view in ('front','back'): shutil.copy2(ROOT/f'art/references/explorer_b_fullbody_v2/{view}.png',REVIEW/f'reference-{view}.png')
for name in ('preview-clay.png','detail-face-clay.png'): shutil.copy2(HD/name,REVIEW/('h31-'+name))
e=html.escape
def figure(file,label):
    width,height=struct.unpack('>II',(REVIEW/file).read_bytes()[16:24])
    return f'<figure><a href="{file}" target="_blank"><img width="{width}" height="{height}" loading="lazy" src="{file}" alt="{e(label)}"></a><figcaption>{e(label)}</figcaption></figure>'
gallery=''.join(figure(n,l) for n,l in names)
findings=''.join(f'<li><b>{e(x["region"])}</b><p>{e(x["observation"])}</p><p class="sub">다음 조치: {e(x["recommendation"])}</p></li>' for x in notes['findings'])
rows=[('생성 모델','Tripo P2-20260801 · Smart Mesh P2 Preview'),('입력','승인된 정면 + 후면 · multiview-to-model'),
 ('설정','quad=true · face_limit=20,000 · seed=20261004'),('실측 면 구성',f'{quads:,} 쿼드 + {triangles:,} 삼각형 = {inspect["polygons"]:,} 폴리곤'),
 ('게임 렌더 기준',f'삼각화 환산 {inspect["triangles"]:,} triangles · {inspect["vertices"]:,} vertices'),
 ('텍스처와 UV','texture=false · pbr=false · 자동 UV 존재, 최종 UV 검수 전'),
 ('실측 비용',f'P2 {result["credits_consumed"]:g} Tripo 크레딧 · 잔액 차이 {result["balance_delta"]:g}'),
 ('이번 전신 실험 합계','H3.1 60 + P2 100 = 160크레딧 · Scenario 0 · 리깅/애니메이션 0')]
table=''.join(f'<tr><th>{e(k)}</th><td>{e(v)}</td></tr>' for k,v in rows)
page=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>탐험가 B · P2 전신 메시 검토</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f4ef;color:#283d36;font:16px/1.8 "Segoe UI","Malgun Gothic",sans-serif}}main{{max-width:1160px;margin:auto;padding:38px 24px 80px}}h1{{font-size:36px;line-height:1.3}}h2{{margin-top:36px}}a{{color:#225e4c}}nav{{display:flex;gap:20px;flex-wrap:wrap;margin:25px 0}}.notice{{background:#fff0d1;padding:20px;border-left:5px solid #af842e}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}}figure{{margin:0;background:white;border-radius:12px;overflow:hidden;border:1px solid #dce3d9}}img{{display:block;width:100%;height:auto}}figcaption{{padding:11px 16px}}table{{width:100%;border-collapse:collapse;background:#fff}}td,th{{padding:12px;border:1px solid #dce3d9;text-align:left}}li{{margin-bottom:24px}}li p{{margin:6px 0}}.sub,small{{color:#626e65}}section{{scroll-margin-top:20px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}h1{{font-size:28px}}}}
</style></head><body><main><small>2026-10-04 · 승인 단계: 전신 3D 형상</small><h1>B형 탐험가<br>Tripo P2 전신 메시</h1><p class="notice"><b>P2로 전신을 다시 생성했습니다. 실제 비용 100크레딧.</b><br>약 2만 쿼드의 FBX 원본과 Blender 검토본입니다. 전신 비율·얼굴·손·발·실제 와이어를 검토할 수 있습니다. 열린 경계와 비정상 연결이 남아 있어 리깅 전 수정이 필요합니다. 원본 메시를 보존했고 사용자 승인 전에는 조립·리깅 단계로 진행하지 않습니다.</p>
<nav><a href="#mesh">실제 모델 보기</a><a href="#findings">검수 결과</a><a href="#spec">설정·비용</a><a href="#compare">H3.1 비교</a><a href="#reference">참조 이미지</a><a download href="review.blend">Blender 파일</a><a download href="model.fbx">원본 FBX</a></nav>
<section id="mesh"><h2>전신 · 얼굴 · 손 · 발 · 와이어</h2><p>모든 화면은 생성된 P2 메시를 Blender에서 직접 렌더했습니다. 이번 단계는 무채색 형상 검토이며, 텍스처가 적용된 화면은 없습니다. 이미지를 누르면 개별 원본을 볼 수 있습니다. 와이어는 실제 폴리곤 경계를 겹친 검수용 렌더입니다.</p><div class="grid">{gallery}</div></section>
<section id="findings"><h2>검수와 다음 조치</h2><ul>{findings}</ul><p class="notice">다음 단계의 순서: 형상 승인 → 필요한 부위 수정·교체 → 별도 머리카락/옷/장식 맞춤 → 최종 UV·텍스처 검토 → 몸·손·얼굴 리깅 → 애니메이션과 Godot 이동 검증. 자동 UV와 쿼드 생성만으로 얼굴 변형, 좌우 대칭, 관절 품질이 검증되지는 않습니다.</p><p><a href="quality-review.json">검수 기록</a> · <a href="topology-detail.json">연결된 메시 섬과 경계 좌표</a></p></section>
<section id="spec"><h2>설정과 실제 차감</h2><table>{table}</table><p>P2를 낮은 면 수로 바로 생성했습니다. 쿼드는 FBX와 Blender 편집본에 보존되어 있습니다. 모델은 1개 객체에 여러 메시 섬이 포함된 상태입니다. 최종 게임 모델이나 리깅 완료 모델이 아닙니다.</p><p><a href="generation-request.json">요청 설정</a> · <a href="generation-result.json">실제 결과 기록</a> · <a href="mesh-inspection.json">Blender 실측</a> · <a href="https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p">공식 P2 API 문서</a></p></section>
<section id="compare"><h2>같은 참조 · H3.1과 P2 형상 비교</h2><p>왼쪽은 먼저 생성한 H3.1 Ultra, 오른쪽은 이번 P2입니다. 각각의 경계에 맞춰 렌더했으므로 픽셀 크기나 카메라 배율이 정확히 일치하는 비교는 아닙니다. 텍스처를 끈 형상끼리 비교합니다. 비용은 각각 60 / 100크레딧입니다.</p><div class="grid">{figure('h31-preview-clay.png','이전 H3.1 · 994,178 삼각형')}{figure('preview-clay.png','이번 P2 · 19,943 쿼드 + 1,948 삼각형')}{figure('h31-detail-face-clay.png','H3.1 얼굴 형상')}{figure('detail-face-clay.png','P2 얼굴 형상')}</div></section>
<section id="reference"><h2>승인된 전신 참조</h2><div class="grid">{figure('reference-front.png','정면 참조')}{figure('reference-back.png','후면 참조')}</div></section></main></body></html>'''
page=page.replace('全身 정면','전신 정면')
(REVIEW/'index.html').write_text(page,encoding='utf-8')
summary={'state':'awaiting_user_3d_review','variant':'p2','source_sha256_verified':True,'actual_tripo_credits':result['credits_consumed'],
 'quads':quads,'triangles':triangles,'render_triangles':inspect['triangles'],'render_count':len(names),
 'source_mesh':source.relative_to(ROOT).as_posix(),'review_blend':(OUT/'review.blend').relative_to(ROOT).as_posix(),
 'rigged':False,'geometry_edited':False,'texture_generated':False,'report_url':'http://127.0.0.1:8842/character-fullbody-p2/'}
save(OUT/'review-summary.json',summary)
plan=read(CHAR/'production-plan.json')
plan.update(state='p2_fullbody_awaiting_user_review',active_generation_variant='p2',
 user_model_choice={'model':'P2-20260801','evidence':'2026-10-04 user: tripo p2를 이용하세요.'},
 generation_variants={'hd':{'credits':60,'source_mesh':(HD/'model.glb').relative_to(ROOT).as_posix(),'preserved':True},'p2':summary},
 next_action='User review of P2 fullbody geometry before selective fixes, clothing fitting, final UV/texture or rigging.')
save(CHAR/'production-plan.json',plan)
print(json.dumps(summary,ensure_ascii=False))
