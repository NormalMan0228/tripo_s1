import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/references/explorer_b_open_mouth_v1'
SOURCE = Path(r'C:\Users\dd\.codex\generated_images\01a0f276-190b-72b3-bbcb-8277fd264084\exec-50c4a4a9-4064-4cf5-ad08-079a15c84edb.png')
IMAGE = OUT / '01_head_open_mouth_front.png'
OUT.mkdir(parents=True, exist_ok=True)
shutil.copy2(SOURCE, IMAGE)
manifest = {
    'date': '2026-10-04',
    'status': 'user_image_review_pending',
    'image': IMAGE.relative_to(ROOT).as_posix(),
    'prompt_file': 'art/references/explorer_b_open_mouth_v1/prompts.json',
    'identity_source': 'art/references/explorer_b_hybrid_hair_hd_v1/01_head_neck_clavicle_smartmesh.png',
    'request': 'Generate an open-mouth head in Tripo from the source image, instead of opening the closed-mouth generated head afterward.',
    'inspection': 'Front view; mouth visibly open; upper/lower lips separated; oral cavity, upper/lower tooth edges and tongue visible; bald head, no brows/lashes; neck ends at clavicles.',
    'next_model': 'Tripo Smart Mesh P2',
    'existing_hair_and_brow_lash_assets': 'retain for refitting after head geometry review',
    'review_gate_source': 'User instruction: review newly generated images before Tripo submission.',
    'tripo_submitted': False,
    'tripo_credits_spent': 0,
    'generation_checks': ['Oral opening must be real geometry, not a painted patch', 'Inspect cavity depth, lip boundary and any teeth/skin fusion', 'Inspect topology before facial rigging'],
}
def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
save(OUT / 'manifest.json', manifest)
pipeline_path = ROOT / 'art/characters/explorer_b_pipeline_v3/pipeline.json'
pipeline = json.loads(pipeline_path.read_text(encoding='utf-8-sig'))
pipeline['status'] = 'open_mouth_head_reference_user_review_pending'
pipeline['next_head_generation'] = manifest
save(pipeline_path, pipeline)
policy_path = ROOT / 'docs/CHARACTER_GENERATION_POLICY.json'
policy = json.loads(policy_path.read_text(encoding='utf-8-sig'))
policy['current_stage'] = 'open_mouth_head_reference_review'
policy['new_reference_batch'] = 'art/references/explorer_b_open_mouth_v1/manifest.json'
policy['next_head_pose'] = 'relaxed_open_mouth_with_visible_oral_depth'
save(policy_path, policy)
review = ROOT / 'artifacts/production-lab-20261003/review/character-open-mouth-reference'
review.mkdir(parents=True, exist_ok=True)
shutil.copy2(IMAGE, review / 'open.png')
shutil.copy2(ROOT / manifest['identity_source'], review / 'original.png')
shutil.copy2(OUT / 'prompts.json', review / 'prompts.json')
(review / 'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Explorer B · 입을 벌린 원본 검토</title><style>body{font:17px/1.7 system-ui;background:#161b23;color:#eef2f8;max-width:1200px;margin:40px auto;padding:0 24px}h1{font-size:30px}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}figure{margin:0}img{width:100%;border-radius:14px}figcaption{padding:12px 0;color:#d2dbea}a{color:#9dc8ff}p{max-width:900px}@media(max-width:650px){main{grid-template-columns:1fr}}</style><h1>입을 벌린 Tripo 원본 · 이미지 검토</h1><p>기존 캐릭터의 얼굴과 쇄골까지의 범위를 유지하며 입을 벌린 시안입니다. 새 이미지를 직접 검토하시겠다는 지침에 따라, 현재 Tripo에는 제출하지 않았습니다.</p><main><figure><img src="original.png"><figcaption>기존 승인 이미지</figcaption></figure><figure><img src="open.png"><figcaption>새 시안 · 입술 분리 / 구강 깊이 / 치아와 혀</figcaption></figure></main><p>다음 단계: 이미지 확인 → Smart Mesh P2 머리 생성 → 실제 구강 형태와 입술 토폴로지 검사 → 기존 헤어·눈썹·속눈썹 재배치 → 페이스 리깅.</p><p>이미지에서 보이는 입안이 실제 메쉬로 생성됐는지는 생성 후 검사합니다. 현재 시안 제작의 Tripo 사용량은 0크레딧입니다.</p><a href="prompts.json">내장 이미지 생성 도구에 사용한 프롬프트</a> · <a href="../character-hybrid-refined/">기존 v2 모델 검토</a></html>''', encoding='utf-8')
print(json.dumps({'image': str(IMAGE), 'review_url': 'http://127.0.0.1:8842/character-open-mouth-reference/', 'tripo_submitted': False}, ensure_ascii=False))
