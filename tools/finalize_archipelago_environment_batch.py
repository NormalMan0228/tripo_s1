"""Produce a concrete fifteen-model checkpoint without approving it for the user."""
import hashlib
import json
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont
from archipelago_queue import locked_queue

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/maps/archipelago_objects_v1'
LAB=ROOT/'labs/archipelago_object_lab'
queue=json.loads((BASE/'queue.json').read_text(encoding='utf-8'))
batch=queue['active_batch']
OUT=ROOT/batch.get('review_package','art/maps/archipelago_environment_v1')
OUT.mkdir(exist_ok=True,parents=True)
ids=batch['assets']
assert len(ids)==15 and batch['max_observed_concurrent']<=3
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',19)
small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',15)
gallery=[]
reports=[]
credits=0
for angle in ['front','back']:
    sheet=Image.new('RGB',(2400,1200),'#eeeade')
    draw=ImageDraw.Draw(sheet)
    for index,ident in enumerate(ids):
        item=next(i for i in queue['items'] if i['id']==ident)
        folder=BASE/ident;stem=ident.split('_',1)[1]
        mesh=json.loads((folder/'mesh_verification.json').read_text(encoding='utf-8'))
        report=json.loads((folder/'review_verification.json').read_text(encoding='utf-8'))
        assert item['review_status']=='awaiting_user' and mesh.get('material_calibration_version')==1,ident
        assert report['runtime_errors']==0
        assert report.get('review_camera_version')==2,ident
        assert hashlib.sha256((folder/'tripo-original.glb').read_bytes()).hexdigest()==report['source_sha256']
        for filename in ['blender_prepare.log','godot_import.log','godot_capture.log','review_finalize.log']:
            assert not re.search(r'SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error|Traceback', (folder/filename).read_text(encoding='utf-8',errors='replace')), (ident,filename)
        im=Image.open(folder/(stem+'_'+angle+'.png')).convert('RGB')
        assert im.size==(1152,800)
        im.thumbnail((480,333),Image.Resampling.LANCZOS)
        x=(index%5)*480;y=(index//5)*400
        sheet.paste(im,(x+(480-im.width)//2,y))
        draw.text((x+12,y+338),f'{index+1:02d} · {item["name"]}',font=font,fill='#304136')
        draw.text((x+12,y+369),f'높이 {item["target_height_m"]:.2f}m · Tripo P2 · 원본 8K',font=small,fill='#687069')
        if angle=='front':
            gallery.append(json.loads((LAB/'reviews'/(ident+'.json')).read_text(encoding='utf-8')))
            reports.append(report)
            credits+=report['credits_consumed']
    sheet.save(OUT/('batch_contact_sheet.png' if angle=='front' else 'batch_back_qa.png'))
(LAB/'batch_review.json').write_text(json.dumps({'batch':batch['id'],'assets':gallery},ensure_ascii=False,indent=2),encoding='utf-8')
(LAB/'active_review.json').write_text(json.dumps(gallery[0],ensure_ascii=False,indent=2),encoding='utf-8')
summary={'batch':batch['id'],'models':15,'credits_consumed':credits,'max_observed_concurrent':batch['max_observed_concurrent'],
         'review_views':60,'final_runtime_errors':0,'source_hashes_preserved':True,'reports':reports,'status':'awaiting_user'}
(OUT/'batch_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with locked_queue() as latest:
    latest['active_batch']['status']='awaiting_user'
    latest['active_batch']['review_package']=str(OUT.relative_to(ROOT)).replace('\\','/')
print('ENVIRONMENT_BATCH_CHECKPOINT_READY models=15 credits=',credits,'max_concurrent=',batch['max_observed_concurrent'])
