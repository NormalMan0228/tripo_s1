"""Hair v3 approved four-view P2 generation; bounded and resumable."""
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
REF=ROOT/'art/references/explorer_b_hair_multiview_v3'
LEDGER=ROOT/'artifacts/character-hd-restart-20261004/budget.json'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def rel(p):return p.relative_to(ROOT).as_posix()
async def run(op,part):
    version=3
    out=OUT/'hair_v3';out.mkdir(parents=True,exist_ok=True)
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
        faces=5000;image=REF/'front.png'
        payload={'model':'P2-20260801','quad':True,'face_limit':faces,'texture':False,'pbr':False,'export_uv':True,'model_seed':202610047}
        request={**payload,'reference_file':rel(image),'reference_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'route':'/generation/multiview-to-model','reservation_credits':150,'prior_same_model_charge':100,'approval':'User requested regeneration and explicitly selected four-view front/left/back/right input on 2026-10-04. Top/bottom are QA concepts only. Remaining approved 1000-credit character budget.','scope':'developer_shared_geometry_for_later_manual_vs_Faceit_comparison','automatic_resubmit':False}
        save(out/'generation-request.json',request)
        views=('front','left','back','right')
        request['references']=[{'view':v,'file':rel(REF/(v+'.png')),'sha256':hashlib.sha256((REF/(v+'.png')).read_bytes()).hexdigest()} for v in views]
        request['qa_only_views']=['top','bottom']
        request['docs']='https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p'
        save(out/'generation-request.json',request)
        inputs=[{v:await upload(provider,REF/(v+'.png'))} for v in views]
        entry={'state':'intent','reservation':150,'created':time.time(),'balance_before':balance,'request_record':rel(out/'generation-request.json'),'automatic_resubmit':False}
        save(out/'generation-intent.json',entry);data['tasks'][name]=entry;save(LEDGER,data)
        result=await provider.request('POST','/generation/multiview-to-model',{**payload,'inputs':inputs})
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
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['submit','poll']);p.add_argument('part',choices=['hair']);a=p.parse_args()
    try:
        with single_batch():asyncio.run(run(a.operation,a.part))
    except Exception as e:
        print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
