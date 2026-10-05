"""Archive generated references and the user's revised brow/lash workflow."""
from pathlib import Path
import json
import shutil
from html import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/references/explorer_b_hybrid_hair_hd_v1'
GEN = Path('C:/Users/dd/.codex/generated_images/01a0f276-190b-72b3-bbcb-8277fd264084')
REVIEW = ROOT / 'artifacts/production-lab-20261003/review/character-hybrid-hair-hd'
REVIEW.mkdir(parents=True, exist_ok=True)
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

rows = [
 ('head','3c4ca2b0-e00e-40a7-8dfc-ed6e15f941a0','01_head_neck_clavicle_smartmesh.png','얼굴 · 목 · 쇄골','Smart Mesh P2용 디자인 검토'),
 ('hair','c0016e3e-7a80-4c05-8ee8-3f6acff79db0','02_hair_hd_multiview_review.png','머리카락','Tripo HD용 디자인 검토. 6면 시트는 직접 API 입력용이 아닙니다. 하단 그림은 내부 공간을 충분히 입증하지 못하므로 별도 검수가 필요합니다.'),
 ('eyebrow','dbfff2bf-6ddf-41f2-bec8-95212193d729','03_eyebrow_texture_reference.png','한쪽 눈썹','간단한 곡면 메쉬 + UV + 알파 텍스처. 현재 이미지는 흰 배경 참고본입니다.'),
 ('upper_lashes','80770d55-d808-4a8c-88d5-57f67ae6ed37','04_upper_lashes_texture_reference.png','한쪽 위 속눈썹','눈꺼풀을 따라 휘어진 메쉬 + UV + 알파 텍스처. 현재 이미지는 완성 텍스처가 아닙니다.'),
 ('lower_lashes','50bbf0f8-618e-4424-85b9-d3dfc5ec72bc','05_lower_lashes_texture_reference.png','한쪽 아래 속눈썹','짧고 성긴 털 참고. 반대쪽은 미러로 제작하고 깜빡임에 맞춰 변형합니다.'),
]
assets=[]
cards=[]
for key, uid, filename, title, note in rows:
    source=GEN/f'exec-{uid}.png'
    target=OUT/filename
    shutil.copy2(source,target)
    shutil.copy2(target,REVIEW/filename)
    assets.append(dict(prompt_key=key,source=str(source),file=str(target.relative_to(ROOT)),status='user_review_pending',note=note))
    cards.append(f'<article><h2>{escape(title)}</h2><p>{escape(note)}</p><a href="{filename}" target="_blank"><img src="{filename}" alt="{escape(title)}"></a></article>')
write(OUT/'manifest.json',dict(tool='built-in image_gen',status='user_review_pending',tripo_calls=0,prompts='prompts.json',assets=assets,orientation='Brow/lash master: character left, viewer right; mirror for opposite side',revision='Brow and lashes changed from Tripo HD to simple Blender meshes with UV and alpha textures after image generation. Original prompts retained as history.'))
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>캐릭터 이미지 검토</title><style>body{margin:0;background:#edf2f1;color:#21352f;font:17px/1.7 "Malgun Gothic",sans-serif}main{max-width:1200px;margin:auto;padding:30px}article{margin:28px 0;padding:24px;background:white;border-radius:14px}img{display:block;width:100%;max-height:850px;object-fit:contain}h1{font-size:30px}h2{font-size:22px}p{max-width:950px}a{color:#176c56}</style><main><h1>Explorer B · 새 이미지 검토</h1><p>머리카락: Tripo HD / 얼굴과 나머지 파츠: Smart Mesh P2 / 눈썹·속눈썹: 간단한 메쉬 + UV + 알파 텍스처</p><p>사용자 검토 대기 중입니다. 이번 이미지 배치로 Tripo 3D 생성을 호출하지 않았습니다. 이미지를 누르면 원본 크기로 열립니다.</p>'''+''.join(cards)+'</main></html>'
(REVIEW/'index.html').write_text(page,encoding='utf-8')
policy_path=ROOT/'docs/CHARACTER_GENERATION_POLICY.json'
policy=read(policy_path)
policy['user_decision']='머리카락은 Tripo HD, 눈썹·위/아래 속눈썹은 간단한 Blender 메쉬+UV+알파 텍스처, 나머지는 Smart Mesh P2. 새 이미지는 사용자 검토 후 3D 생성.'
policy['generation_mode']='Tripo_HD_hair_P2_other_parts_Blender_texture_cards_brows_lashes'
for k in ['eyebrow','eyelashes_upper','eyelashes_lower']:
    policy['mode_by_part'][k]='Blender simple mesh + UV + alpha texture; no Tripo generation'
policy['topology_preference']='HD hair source; P2 other generated parts; low-poly textured brow/lash cards; inspect facial deformation topology.'
policy['new_reference_batch']='art/references/explorer_b_hybrid_hair_hd_v1/manifest.json'
write(policy_path,policy)
pipeline_path=ROOT/'art/characters/explorer_b_pipeline_v3/pipeline.json'
pipeline=read(pipeline_path)
pipeline['user_direction']['generation_modes']={'HD':['hair'],'Smart Mesh P2':'other generated parts including head-neck-clavicle bust','Blender simple mesh + UV + alpha texture':['eyebrow','eyelashes_upper','eyelashes_lower']}
hair=pipeline['separate_hair_parts']
hair['model_source']='Tripo HD hair; Blender simple UV-mapped textured meshes for brows and lashes'
hair['generation_mode']='per_part; see user_direction.generation_modes'
hair['status']='reference_images_generated_user_review_pending; mesh_and_alpha_texture_work_not_started'
hair['brow_lash_workflow']={'geometry':'One fitted brow surface and separate curved upper/lower lash strips, then mirror','texture':'Transparent alpha hair texture; current white-background images are design references only','rigging':'Bind brows to forehead deformation and lashes to corresponding eyelid deformation; independent left/right controls','validation':['No floating medial lash roots','Blink 0/25/50/75/100 percent','Gaze combined with blink','Alpha edges and transparency in Godot'],'tripo_generation':False}
hair['hair_multiview_policy']='Front/left/back/right individual approved images for generation; top/underside for inspection. Review sheet is not direct API input. Verify HD input support before submitting.'
hair['hair_internal_shape']='Avoid inward spikes, filled face plates, neck plugs and round bowl interiors; inspect fitted head clearance.'
write(pipeline_path,pipeline)
overview=ROOT/'docs/TRIPOTHON_OVERVIEW_20261004.md'
text=overview.read_text(encoding='utf-8-sig')
text=text.replace('참조로 P2에 입력합니다.','참조로 Tripo HD를 사용합니다. 제출 전 HD의 입력 지원을 확인합니다.')
text=text.replace('생성 기준은 계속 Tripo이며, 아래 커브 작업은 다듬기 단계의 제안입니다.','최신 결정은 **머리카락 Tripo HD / 얼굴과 나머지 생성 파츠 Smart Mesh P2 / 눈썹·속눈썹 간단한 Blender 메쉬 + UV + 알파 텍스처**입니다. 눈썹·속눈썹은 Tripo로 생성하지 않습니다. 새 이미지는 사용자가 검토한 후 3D 생성에 사용합니다.')
text=text.replace('이를 Tripo 얼굴의 별도 눈썹·속눈썹에 시험하는 것이 우선 제안이며, 아직 적용·검증 결과는 아닙니다.','현재 눈썹·속눈썹은 간단한 메쉬와 알파 텍스처 방식이 우선이며, 이 커브 기능들은 필요할 때 검토할 후보입니다. 아직 적용·검증 결과는 아닙니다.')
overview.write_text(text,encoding='utf-8')
print('Saved 5 images, manifest, review gallery and updated workflow records.')
