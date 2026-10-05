"""Generate reviewed head/hand/hair references as native P2 quad sources only."""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_dev_character import upload
from detail_map_tripo import ledger,save,LEDGER
from generate_modular_character_parts import single_batch
import generate_fullbody_base as native_download

CHAR=ROOT/'art/characters/explorer_b_fullbody_v2'
OUT=CHAR/'04_replacement_parts_p2'
SELECTION=ROOT/'art/references/explorer_b_modular_v1/final_images_selection.json'
REF=SELECTION.parent/'final_images'
PARTS={'head':6000,'hand':4000,'hair':4000}
RESERVATION=150
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
relative=lambda p:p.relative_to(ROOT).as_posix()

async def run(operation,part):
    out=OUT/part;out.mkdir(parents=True,exist_ok=True)
    plan=read(CHAR/'production-plan.json')
    if plan.get('user_model_choice',{}).get('model')!='P2-20260801':raise ProviderError('model_choice_not_recorded')
    original_plan=read(ROOT/'art/characters/explorer_b_modular_v1/production-plan.json')
    if not next(s for s in original_plan['stages'] if s['id']=='references')['review']['approved']:
        raise ProviderError('reference_requires_review')
    item=next(x for x in read(SELECTION)['assets'] if x['id']==part)
    image=REF/item['file']
    if hashlib.sha256(image.read_bytes()).hexdigest()!=item['sha256']:raise ProviderError('approved_reference_changed')
    provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
    data=ledger();bucket=data['buckets']['character_detail'];name='explorer-replacement-p2-quad-'+part+'-v2'
    entry=bucket['tasks'].get(name)
    if operation=='submit':
        if entry:
            if not entry.get('task_id'):raise ProviderError('ambiguous_intent_no_resubmit')
            print(json.dumps({'state':'existing_task_preserved','part':part,'task_id':entry['task_id']}));return
        if (out/'generation-intent.json').exists():raise ProviderError('ambiguous_intent_no_resubmit')
        committed=sum(float(t.get('credits_consumed',t['reservation'])) if isinstance(t.get('credits_consumed',t['reservation']),(int,float)) else t['reservation'] for t in bucket['tasks'].values())
        if committed+RESERVATION>bucket['tripo_cap']:raise ProviderError('experiment_budget_exhausted')
        balance=await provider.balance()
        if balance<RESERVATION:raise ProviderError('insufficient_balance')
        token=await upload(provider,image)
        payload={'input':token,'model':'P2-20260801','quad':True,'face_limit':PARTS[part],
                 'texture':False,'pbr':False,'export_uv':True,'model_seed':20261004}
        request={k:v for k,v in payload.items() if k!='input'}
        request.update(route='/generation/image-to-model',part=part,reference_file=relative(image),
            reference_sha256=item['sha256'],reservation_credits=RESERVATION,
            approval_evidence='2026-10-04 user: 앞으로 p2를 쓸 겁니다. 이제 머리, 손 등을 따로 만들어 봅시다',
            scope='developer_independent_geometry_review_only',automatic_resubmit=False)
        save(out/'generation-request.json',request)
        entry={'state':'intent','reservation':RESERVATION,'created':time.time(),'balance_before':balance,'automatic_resubmit':False}
        save(out/'generation-intent.json',entry);bucket['tasks'][name]=entry;save(LEDGER,data)
        response=await provider.request('POST','/generation/image-to-model',payload)
        task_id=response.get('task_id')
        if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',task_id):raise ProviderError('upstream_schema',uncertain=True)
        entry.update(state='submitted',task_id=task_id);save(LEDGER,data);save(out/'generation-task.json',{'task_id':task_id})
        print(json.dumps({'part':part,'state':'submitted','task_id':task_id,'reservation':RESERVATION}));return
    if not entry or not entry.get('task_id'):raise ProviderError('no_submitted_task')
    task=await provider.task(entry['task_id']);status=task.get('status')
    safe={'part':part,'task_id':entry['task_id'],'status':status,'progress':task.get('progress'),'credits_consumed':task.get('credits_consumed')}
    if status in ('success','failed','cancelled'):
        entry['state']=status
        if isinstance(task.get('credits_consumed'),(int,float)):entry['credits_consumed']=task['credits_consumed']
        save(LEDGER,data)
        safe.update(balance_before=entry['balance_before'],balance_after=await provider.balance())
        # Several independently authorized tasks may overlap. Task charge is primary.
        safe['balance_delta_includes_other_tasks']=safe['balance_before']-safe['balance_after']
        if status=='success':
            native_download.OUT=out
            existing=[out/('model.'+e) for e in ('fbx','glb','zip') if (out/('model.'+e)).exists()]
            model=existing[0] if existing else await native_download.download_native(task.get('output',{}).get('model_url',''))
            safe.update(file=relative(model),bytes=model.stat().st_size,sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                        rigged=False,assembled=False,texture_generated=False,user_geometry_approved=False)
        save(out/'generation-result.json',safe)
    else:save(out/'generation-status.json',safe)
    print(json.dumps(safe))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['submit','poll']);p.add_argument('part',choices=list(PARTS))
    a=p.parse_args()
    try:
        with single_batch():asyncio.run(run(a.operation,a.part))
    except (ProviderError,ValueError) as e:
        print(json.dumps({'error':e.code if isinstance(e,ProviderError) else 'invalid_configuration','automatic_resubmit':False}));sys.exit(1)
