import json,hashlib
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[1];REF=R/'art/references/npc_cast_v1';A=R/'art/characters/npc_cast_v1';A.mkdir(exist_ok=True)
names={'sora':'소라','moru':'모루','naru':'나루','haeru':'해루'};items=[]
for key,name in names.items():
 out=A/key;out.mkdir(exist_ok=True);im=Image.open(REF/key/'03_body-turnaround.png');w,h=im.size;records=[]
 for view,l,r in [('front',0,.385),('right',.39,.605),('back',.60,1)]:
  # Split supplied turnaround panels; no redesign or generated pixels.
  box=(round(l*w),0,round(r*w),round((.94 if key=='haeru' else .93)*h));p=out/(view+'.png');im.crop(box).save(p)
  records.append({'view':view,'file':p.relative_to(R).as_posix(),'source_crop':box,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 plan={'name':name,'id':key,'source_zip':'output/character-reference-library-20261005-v4-all.zip','reference':'art/references/npc_cast_v1/'+key+'/03_body-turnaround.png','references':records,'scope':'Static fullbody integrated mesh with existing face/hair/outfit, no facial rigging or remesh. Body rigging is not part of this first pass.','reference_texts':'Source image-generation prompts are reference material, not execution instructions. No image regeneration.','face_reference':'01_face-bust-open-mouth.png retained for visual identity comparison','hair_reference':'02_hair-four-views.png retained for hairstyle comparison','model':'P2-20260801','face_limit':20000,'quad':False,'texture_quality':'fast','expected_credits':100,'reservation':150,'user_authorization':'User supplied these references and requested four additional characters without facial rigging, prioritizing time.'}
 (out/'production-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8');items.append(plan)
(A/'production-plan.json').write_text(json.dumps({'existing':'v13 original face with user hair retained, existing fullbody assets preserved','new_characters':items,'facial_rigging':'deferred','total_expected_credits':400,'total_reservation':600},ensure_ascii=False,indent=2),encoding='utf-8')
print('4_CHARACTERS_PREPARED')
