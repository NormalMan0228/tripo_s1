import json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];REF=R/'art/references/npc_cast_closed_v2';G=Path('C:/Users/dd/.codex/generated_images/01a0f276-190b-72b3-bbcb-8277fd264084')
files={'sora':'exec-3bdab458-016a-456e-b761-3d8c1a5d7438.png','moru':'exec-641e6f63-5dd5-48b5-9274-68e44e8cd604.png','naru':'exec-77d926fa-f338-4bb4-8350-c6396e564f5b.png','haeru':'exec-22f8a984-1e23-445b-a8b1-66816bf2ff84.png'}
for k,f in files.items():
 d=REF/k;d.mkdir(exist_ok=True,parents=True);shutil.copy2(G/f,d/'03_body-turnaround.png')
 (d/'image-generation.json').write_text(json.dumps({'tool':'built-in image_gen','source':'art/references/npc_cast_v1/'+k+'/03_body-turnaround.png','edit':'Close front/profile mouth, slight relaxed smile, no teeth or tongue. Preserve identity, hairstyle, outfit, anatomy, A-pose and view layout.','user_authorization':'그리고 입을 다문 이미지를 생성해서 만드세요.','generation_path':str(G/f)},ensure_ascii=False,indent=2),encoding='utf-8')
for src,dst in [('prepare_npc_cast_v1.py','prepare_npc_closed_v2.py'),('generate_npc_cast_v1.py','generate_npc_closed_v2.py')]:
 t=(R/'tools'/src).read_text(encoding='utf-8').replace('npc_cast_v1','npc_cast_closed_v2').replace('npc_cast_v1_','npc_cast_closed_v2_').replace('face-bust-open-mouth','face-bust-closed').replace('>=150','>=110').replace('+150','+110').replace("'reservation':150","'reservation':110").replace('expected_credits\':100','expected_credits\':110').replace('total_expected_credits\':400','total_expected_credits\':440').replace('total_reservation\':600','total_reservation\':440').replace('prioritizing time.','prioritizing time, explicitly requested closed-mouth generated references.').replace('User explicitly selected integrated fullbody first on 2026-10-05','User selected integrated fullbody and explicitly requested generated closed-mouth references on 2026-10-05')
 (R/'tools'/dst).write_text(t,encoding='utf-8')
for k in ['sora','moru']:
 p=R/'art/characters/npc_cast_v1'/k/'production-plan.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(accepted=False,superseded_by='npc_cast_closed_v2',reason='User requested closed mouth after first submissions');p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('CLOSED_MOUTH_REFERENCES_SAVED')
