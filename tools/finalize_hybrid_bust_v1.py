from pathlib import Path
import json,shutil,hashlib
from html import escape
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v1';REF=R/'art/references/explorer_b_hybrid_hair_hd_v1'
WEB=R/'artifacts/production-lab-20261003/review/character-hybrid-hair-hd'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ledger=read(R/'artifacts/character-hd-restart-20261004/budget.json')
total=sum(t.get('credits_consumed',t['reservation']) for t in ledger['tasks'].values())
report=read(O/'assembly-report.json');report['budget_remaining']=ledger['tripo_cap']-total
report['sources']={p:read(O/p/'generation-result.json') for p in ('head','hair')}
report['verified_api_docs']=['https://developers.tripo3d.ai/en/docs/generation-image-to-model/p','https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard']
save(O/'assembly-report.json',report)
ref=read(REF/'manifest.json');ref['status']='user_approved_designs_generation_completed';ref['approval']='2026-10-04: 좋습니다...그럼 만들어보세요';ref['tripo_calls']=2;ref['production_input_note']='Imagegen prepared individual view assets from approved sheet without an intentional design change. These are not pixel-identical crops.';ref['production_prompts']='production-prompts.json';ref['model_output']=str(O.relative_to(R));save(REF/'manifest.json',ref)
pipeline_path=R/'art/characters/explorer_b_pipeline_v3/pipeline.json';pipeline=read(pipeline_path)
pipeline['status']='hybrid_bust_static_assembly_user_review_pending'
pipeline['separate_hair_parts']['status']='HD_hair_and_P2_head_generated; mirrored_UV_alpha_brow_lash_meshes_created; static_fit_only'
pipeline['current_hybrid_bust']={'blend':str((O/'explorer_b_hybrid_bust_v1.blend').relative_to(R)),'report':str((O/'assembly-report.json').relative_to(R)),'facial_rigging':'pending_geometry_review','api_credits':140,'budget_remaining':ledger['tripo_cap']-total}
save(pipeline_path,pipeline)
policy_path=R/'docs/CHARACTER_GENERATION_POLICY.json';policy=read(policy_path);policy['current_stage']='hybrid_bust_geometry_and_static_assembly_review';policy['new_HD_generation_submitted']=True;policy['current_hybrid_output']=str(O.relative_to(R));policy['current_batch_actual_credits']=total;save(policy_path,policy)
for f in ['front.png','angle.png','side.png','face_cards.png','explorer_b_hybrid_bust_v1.blend','assembly-report.json']:
    shutil.copy2(O/f,WEB/f)
shutil.copy2(REF/'production_inputs/brow_lash_atlas.png',WEB/'brow_lash_atlas.png')
old=WEB/'index.html';original=WEB/'reference-images.html'
if not original.exists():shutil.copy2(old,original)
cards=''.join(f'<article><h2>{title}</h2><a href="{file}" target="_blank"><img src="{file}" alt="{title}"></a></article>' for file,title in [('front.png','정면'),('angle.png','사선'),('side.png','측면'),('face_cards.png','헤어를 숨긴 눈썹·속눈썹 배치'),('brow_lash_atlas.png','공유 RGBA 텍스처 아틀라스')])
old.write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Explorer B · 하이브리드 조립본</title><style>body{margin:0;background:#edf2f1;color:#233b32;font:17px/1.8 "Malgun Gothic",sans-serif}main{max-width:1100px;margin:auto;padding:32px}article{padding:24px;background:white;border-radius:16px;margin:24px 0}img{display:block;width:100%;max-height:850px;object-fit:contain}a{color:#12694e}nav{display:flex;gap:24px;flex-wrap:wrap}.note{background:#fff5da;padding:20px;border-radius:12px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}</style><main><h1>Explorer B · 하이브리드 조립본</h1><p>Tripo 원본을 보존한 새 Blender 파일입니다. 형상·배치 검토 단계입니다.</p><nav><a href="explorer_b_hybrid_bust_v1.blend">Blender 파일</a><a href="reference-images.html">승인한 디자인</a><a href="assembly-report.json">작업 기록</a></nav><table><tr><th>부품</th><th>제작 방식</th><th>현재 상태</th></tr><tr><td>얼굴·목·쇄골</td><td>Tripo P2, 15,836면</td><td>불필요한 하단 제거와 면 방향 보정</td></tr><tr><td>머리카락</td><td>Tripo HD, 471,836삼각면</td><td>4방향 생성, 머리에 크기·위치 맞춤</td></tr><tr><td>눈썹·위/아래 속눈썹</td><td>간단한 UV 메쉬 + RGBA 텍스처</td><td>한쪽씩 제작 후 미러, 양쪽 합계 384사각면</td></tr></table><p>이번 Tripo 사용: 140크레딧 · 승인 한도 잔여: 180크레딧</p><p class="note">페이스 리깅·깜빡임은 아직 없습니다. 얼굴 색상은 승인 이미지를 정면 투영한 검토용 재질이며, 최종 텍스처가 아닙니다. 헤어는 고해상도 원본 단계로 게임용 리토폴로지가 필요합니다. 헤어 간섭·속눈썹 뿌리·안구 주변은 리깅 전 추가 검토 대상입니다.</p>'''+cards+'</main></html>',encoding='utf-8')
print(json.dumps({'status':'saved','credits':140,'remaining':ledger['tripo_cap']-total,'blend':str(O/'explorer_b_hybrid_bust_v1.blend')}))
