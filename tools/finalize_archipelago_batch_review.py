"""Assemble a 15-object review gallery without approving it for the user."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from archipelago_queue import locked_queue

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/maps/archipelago_objects_v1'
LAB=ROOT/'labs/archipelago_object_lab'
queue=json.loads((BASE/'queue.json').read_text(encoding='utf-8'))
batch=queue['active_batch']
assert len(batch['assets'])==15
assert batch['max_observed_concurrent']<=3
items=[next(i for i in queue['items'] if i['id']==asset) for asset in batch['assets']]
assert all(i['review_status']=='approved' for i in queue['items'][:2])
assert all(i['review_status']=='planned' for i in queue['items'][17:])
assert all(i['review_status']=='awaiting_user' for i in items)
out=BASE/batch['id']
out.mkdir(exist_ok=True)
gallery=[]
reports=[]
sheet=Image.new('RGB',(2400,1200),'#eeeade')
draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',20)
for n,item in enumerate(items):
    folder=BASE/item['id']
    report=json.loads((folder/'review_verification.json').read_text(encoding='utf-8'))
    assert report['runtime_errors']==0 and report['embedded_pbr_textures']
    assert hashlib.sha256((folder/'tripo-original.glb').read_bytes()).hexdigest()==report['source_sha256']
    spec=json.loads((LAB/'reviews'/(item['id']+'.json')).read_text(encoding='utf-8'))
    gallery.append(spec)
    reports.append(report)
    stem=item['id'].split('_',1)[1]
    with Image.open(folder/(stem+'_front.png')) as im:
        # Layout for reviewing actual engine captures, never alter a source reference.
        thumb=im.convert('RGB').resize((480,333),Image.Resampling.LANCZOS)
        x=(n%5)*480
        y=(n//5)*400
        sheet.paste(thumb,(x,y))
        draw.text((x+15,y+346),item['id'].split('_')[0]+' · '+item['name'],font=font,fill='#26342c')
sheet.save(out/'batch_contact_sheet.png')
payload={'batch':batch['id'],'assets':gallery}
(LAB/'batch_review.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
(LAB/'active_review.json').write_text(json.dumps(gallery[0],ensure_ascii=False,indent=2),encoding='utf-8')
report={'batch':batch['id'],'review_status':'awaiting_user','count':len(items),
        'credits_consumed':sum(r['credits_consumed'] for r in reports),
        'max_observed_concurrent':batch['max_observed_concurrent'],
        'views_verified':sum(len(r['views']) for r in reports),
        'original_hashes_verified':True,'runtime_errors':0,'assets':reports}
(out/'batch_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
with locked_queue() as latest:
    latest['active_batch']['status']='awaiting_user'
    latest['active_batch']['review_package']=str(out.relative_to(ROOT)).replace('\\','/')
print('BATCH_REVIEW_READY',json.dumps({k:v for k,v in report.items() if k!='assets'}),flush=True)
