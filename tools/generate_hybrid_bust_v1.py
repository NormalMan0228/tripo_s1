"""Approved hybrid bust: P2 head and HD four-view hair. Bounded, no resubmits."""
import argparse, asyncio, hashlib, json, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_dev_character import upload
from generate_modular_character_parts import single_batch
from generate_hd_character_restart import save
import generate_fullbody_base as native
OUT=ROOT/'art/characters/explorer_b_hybrid_bust_v1'
REF=ROOT/'art/references/explorer_b_hybrid_hair_hd_v1'
LEDGER=ROOT/'artifacts/character-hd-restart-20261004/budget.json'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
async def run(op,part):
    out=OUT/part;out.mkdir(parents=True,exist_ok=True)
    data=read(LEDGER);name='hybrid_bust_v1_'+part;entry=data['tasks'].get(name)
    provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
    if op=='submit':
        if entry or (out/'generation-intent.json').exists():
            if not entry or not entry.get('task_id'):raise ProviderError('ambiguous_intent_no_resubmit')
            print(json.dumps({'state':'existing_task_preserved','part':part,'task_id':entry['task_id']}));return
        reservation=150 if part=='head' else 60
        committed=sum(float(t.get('credits_consumed',t['reservation'])) for t in data['tasks'].values())
        if committed+reservation>data['tripo_cap']:raise ProviderError('budget_exhausted')
        balance=await provider.balance()
        if balance<reservation:raise ProviderError('insufficient_balance')
        if part=='head':
            refs=[('front',REF/'01_head_neck_clavicle_smartmesh.png')]
            payload={'model':'P2-20260801','quad':True,'face_limit':15000,'texture':False,'pbr':False,'export_uv':True,'enable_image_autofix':False,'model_seed':202610049}
            route='/generation/image-to-model'
        else:
            refs=[(v,REF/'production_inputs'/('hair_'+v+'.png')) for v in ('front','left','back','right')]
            payload={'model':'v3.1-20260211','geometry_quality':'detailed','face_limit':500000,'quad':False,'smart_low_poly':False,'texture':False,'pbr':False,'export_uv':False,'model_seed':202610049}
            route='/generation/multiview-to-model'
        request={**payload,'route':route,'references':[{'view':v,'path':rel(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for v,p in refs],'reservation':reservation,'user_authorization':'2026-10-04: 좋습니다...그럼 만들어보세요. Approved displayed design images; existing additional 1000-credit cap. Brows/lashes are Blender textured meshes, not Tripo tasks.','automatic_resubmit':False}
        save(out/'generation-request.json',request)
        tokens=[(v,await upload(provider,p)) for v,p in refs]
        if part=='head':payload['input']=tokens[0][1]
        else:payload['inputs']=[{v:t} for v,t in tokens]
        entry={'state':'intent','reservation':reservation,'created':time.time(),'balance_before':balance,'request_record':rel(out/'generation-request.json'),'automatic_resubmit':False}
        save(out/'generation-intent.json',entry);data['tasks'][name]=entry;save(LEDGER,data)
        result=await provider.request('POST',route,payload)
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
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['submit','poll']);p.add_argument('part',choices=['head','hair']);a=p.parse_args()
    try:
        with single_batch():asyncio.run(run(a.operation,a.part))
    except Exception as e:
        print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
