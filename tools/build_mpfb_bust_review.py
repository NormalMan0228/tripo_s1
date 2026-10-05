"""Package the rendered bust views for a quick design review."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/mpfb-clavicle-bust-20261004'
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',23)
small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
items=[('front','정면 · 기본 표정'),('three_quarter','3/4 · 얼굴과 목 연결'),('profile','측면 · 입과 턱'),('blink','눈 감기 · 속눈썹 연동'),('smile','미소'),('mouth_open','입 벌리기')]
sheet=Image.new('RGB',(1260,1050),'#192327');d=ImageDraw.Draw(sheet)
d.text((24,16),'쇄골 흉상 v1 · MPFB 기반 구조 검토',font=font,fill='white')
d.text((24,53),'기존 디자인 참고 / 유료 API 사용 없음 / 18초 표정 검토 시퀀스',font=small,fill='#b6c6ce')
for index,(stem,title) in enumerate(items):
 x=(index%3)*420;y=96+(index//3)*473
 im=Image.open(OUT/(stem+'.png')).convert('RGB');im.thumbnail((408,438))
 sheet.paste(im,(x+(420-im.width)//2,y))
 d.text((x+16,y+438),title,font=small,fill='white')
sheet.save(OUT/'contact-sheet.jpg',quality=94)

pipeline=ROOT/'art/characters/explorer_b_pipeline_v3/pipeline.json'
data=json.loads(pipeline.read_text(encoding='utf-8-sig'))
if data.get('model_origin')=='tripo':
 # Rebuilding a historical test sheet must not undo the user's pipeline choice.
 print(OUT/'contact-sheet.jpg')
 raise SystemExit(0)
data['status']='free_addons_installed; template_test_passed; styled_clavicle_bust_v1_created; visual_design_approval_and_engine_export_pending'
data['clavicle_bust']={
 'version':1,'date':'2026-10-04','status':'design_review',
 'blend':'art/characters/explorer_b_pipeline_v3/02_clavicle_bust/explorer_b_clavicle_bust_v1.blend',
 'reference':'art/references/explorer_b_faceit_comparison_v1/03_head_neck_clavicle.png',
 'launcher':'Character_Clavicle_Bust_Blender.cmd',
 'review':'artifacts/mpfb-clavicle-bust-20261004/contact-sheet.jpg',
 'verification':'artifacts/mpfb-clavicle-bust-20261004/verification.json',
 'neutral':'closed lips, open eyes','skin_base_vertices':4635,'facial_units':52,
 'animation':'18-second slowed shape-key review; no skeletal facial rig in this isolated bust',
 'limitations':['Proportions remain a design review draft, not an exact reference reconstruction.','Only listed basic expressions and combinations were checked; the entire 89-target library is not artistically validated.','No game-engine export performed.'],
 'paid_api_calls':0}
pipeline.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(OUT/'contact-sheet.jpg')
