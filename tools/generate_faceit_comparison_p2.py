"""Approved head and hair, P2 native quads; bounded, resumable, no secret output."""
import argparse, asyncio, hashlib, json, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from generate_dev_character import upload
from generate_modular_character_parts import single_batch
from generate_hd_character_restart import save
import generate_fullbody_base as native
OUT=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
REF=ROOT/'art/references/explorer_b_faceit_comparison_v1'
LEDGER=ROOT/'artifacts/character-hd-restart-20261004/budget.json'
PARTS={'head':('03_head_neck_clavicle.png',15000),'hair':('04_hair_front.png',4000)}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def rel(p):return p.relative_to(ROOT).as_posix()
async def run(op,part,hair_retry=False):
    if hair_retry and part!='hair':raise ProviderError('retry_only_authorized_for_hair')
    version=2 if hair_retry else 1
    out=OUT/('hair_v2' if hair_retry else part);out.mkdir(parents=True,exist_ok=True)
    data=read(LEDGER);name='faceit_comparison_p2_'+part+'_v'+str(version);entry=data['tasks'].get(name)
    provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
    if op=='submit':
        if entry or (out/'generation-intent.json').exists():
            if not entry or not entry.get('task_id'):raise ProviderError('ambiguous_intent_no_resubmit')
            print(json.dumps({'state':'existing_task_preserved','part':part,'task_id':entry['task_id']}));return
        committed=sum(float(t.get('credits_consumed',t['reservation'])) for t in data['tasks'].values())
        if committed+150>data['tripo_cap']:raise ProviderError('budget_exhausted')
        balance=await provider.balance()
        if balance<150:raise ProviderError('insufficient_balance')
        file,faces=PARTS[part];image=REF/file
        payload={'model':'P2-20260801','quad':True,'face_limit':faces,'texture':False,'pbr':False,'export_uv':True,'enable_image_autofix':False,'model_seed':202610046 if hair_retry else 202610045}
        request={**payload,'reference_file':rel(image),'reference_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'route':'/generation/image-to-model','reservation_credits':150,'prior_same_model_charge':100,'approval':'User approved head/neck and hair images, then requested Tripo P2 Smart Mesh like Stefan. Uses remaining additional 1000 credit character budget.','scope':'developer_shared_geometry_for_later_manual_vs_Faceit_comparison','automatic_resubmit':False}
        if hair_retry:
            request.update(approval='User: 머리카락은 재생성 해야겠습니다. Same approved image and P2 settings, new seed; preserve v1.',previous_source=rel(OUT/'hair/model.fbx'))
        save(out/'generation-request.json',request)
        token=await upload(provider,image)
        entry={'state':'intent','reservation':150,'created':time.time(),'balance_before':balance,'request_record':rel(out/'generation-request.json'),'automatic_resubmit':False}
        save(out/'generation-intent.json',entry);data['tasks'][name]=entry;save(LEDGER,data)
        result=await provider.request('POST','/generation/image-to-model',{**payload,'input':token})
        tid=result.get('task_id')
        if not isinstance(tid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',tid):raise ProviderError('upstream_schema',uncertain=True)
        entry.update(state='submitted',task_id=tid);save(LEDGER,data);save(out/'generation-task.json',{'task_id':tid})
        print(json.dumps({'part':part,'status':'submitted','task_id':tid}));return
    if not entry or not entry.get('task_id'):raise ProviderError('no_task')
    task=await provider.task(entry['task_id'])
    safe={'part':part,'task_id':entry['task_id'],'status':task.get('status'),'progress':task.get('progress'),'credits_consumed':task.get('credits_consumed')}
    if safe['status'] in ('success','failed','cancelled'):
        entry['state']=safe['status']
        if isinstance(safe['credits_consumed'],(int,float)):entry['credits_consumed']=safe['credits_consumed']
        save(LEDGER,data)
        safe['budget_remaining']=data['tripo_cap']-sum(float(t.get('credits_consumed',t['reservation'])) for t in data['tasks'].values())
        if safe['status']=='success':
            existing=[out/('model.'+e) for e in ('fbx','glb','zip') if (out/('model.'+e)).exists()]
            native.OUT=out
            file=existing[0] if existing else await native.download_native(task.get('output',{}).get('model_url',''))
            safe.update(file=rel(file),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),rigged=False,texture_generated=False,assembled=False)
        save(out/'generation-result.json',safe)
    else:save(out/'generation-status.json',safe)
    print(json.dumps(safe))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['submit','poll']);p.add_argument('part',choices=PARTS);p.add_argument('--hair-retry',action='store_true');a=p.parse_args()
    try:
        with single_batch():asyncio.run(run(a.operation,a.part,a.hair_retry))
    except Exception as e:
        print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
