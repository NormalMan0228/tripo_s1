"""One reviewed front/back developer body generation, resumable without resubmit."""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from urllib.parse import urlparse
import httpx
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools'))
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_dev_character import upload,quarantine_download
from detail_map_tripo import ledger,save,LEDGER
from generate_modular_character_parts import single_batch

CHAR=ROOT/'art/characters/explorer_b_fullbody_v2'
OUT=CHAR/'03_generated'
REF=ROOT/'art/references/explorer_b_fullbody_v2'
NAME='explorer-fullbody-hd-v2'
RESERVATION=100
BUCKET='character_detail'
VARIANT='hd'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def relative(p): return p.relative_to(ROOT).as_posix()

async def download_native(url):
    """Preserve quad-capable output; do not relabel FBX as GLB."""
    parsed=urlparse(url);host=parsed.hostname or ''
    if parsed.scheme!='https' or parsed.port not in (None,443) or not (
        host=='tripo3d.ai' or host.endswith('.tripo3d.ai') or host=='tripo-data.rg1.data.tripo3d.com'):
        raise ProviderError('unsafe_asset_url')
    async with httpx.AsyncClient(timeout=90,follow_redirects=False) as client:
        response=await client.get(url)
    blob=response.content
    if response.status_code!=200 or not 12<len(blob)<80*1024*1024:
        raise ProviderError('developer_asset_download_failed')
    if blob[:4]==b'glTF': ext='glb'
    elif blob.startswith(b'Kaydara FBX Binary') or blob[:200].lstrip().startswith(b'; FBX'): ext='fbx'
    elif blob[:4]==b'PK\x03\x04': ext='zip'
    else: raise ProviderError('unsupported_native_format')
    target=OUT/('model.'+ext);target.write_bytes(blob)
    return target

async def run(operation):
    OUT.mkdir(parents=True,exist_ok=True)
    plan=read(CHAR/'production-plan.json')
    if not plan.get('reference_review',{}).get('approved'):
        raise ProviderError('references_not_approved')
    record=read(REF/'generation-record.json')
    for item in record['images']:
        if hashlib.sha256((REF/item['file']).read_bytes()).hexdigest()!=item['sha256']:
            raise ProviderError('approved_reference_changed')
    provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
    data=ledger()
    bucket=data['buckets'][BUCKET]
    entry=bucket['tasks'].get(NAME)
    if operation=='submit':
        if entry:
            if not entry.get('task_id'): raise ProviderError('ambiguous_intent_no_resubmit')
            print(json.dumps({'state':'existing_task_preserved','task_id':entry['task_id']}));return
        if (OUT/'generation-intent.json').exists(): raise ProviderError('ambiguous_intent_no_resubmit')
        committed=sum(float(t.get('credits_consumed',t['reservation'])) if isinstance(t.get('credits_consumed',t['reservation']),(int,float)) else t['reservation'] for t in bucket['tasks'].values())
        if committed+RESERVATION>bucket['tripo_cap']: raise ProviderError('experiment_budget_exhausted')
        balance=await provider.balance()
        if balance<RESERVATION: raise ProviderError('insufficient_balance')
        tokens=[await upload(provider,REF/name) for name in ('front.png','back.png')]
        payload={'inputs':[{'front':tokens[0]},{'back':tokens[1]}],
          'model':'v3.1-20260211','geometry_quality':'detailed','face_limit':1000000,
          'texture':True,'pbr':True,'texture_quality':'detailed','texture_version':'v3.0-20250812',
          'quad':False,'smart_low_poly':False,'generate_parts':False,'export_uv':True,
          'orientation':'align_image','texture_alignment':'original_image','model_seed':20261004,
          'texture_seed':20261004}
        if VARIANT=='p2':
            payload={'inputs':[{'front':tokens[0]},{'back':tokens[1]}],
              'model':'P2-20260801','face_limit':20000,'quad':True,
              'texture':False,'pbr':False,'export_uv':True,'model_seed':20261004}
        request={k:v for k,v in payload.items() if k!='inputs'}
        request.update(route='/generation/multiview-to-model',reference_files=[relative(REF/'front.png'),relative(REF/'back.png')],
          documented_estimate_credits=60 if VARIANT=='hd' else None,reservation_credits=RESERVATION,
          source='https://developers.tripo3d.ai/en/models/v3-1' if VARIANT=='hd' else 'https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p',
          scope='developer_high_resolution_source_not_runtime_character' if VARIANT=='hd' else 'developer_P2_quad_geometry_review_before_texture')
        save(OUT/'generation-request.json',request)
        entry={'reservation':RESERVATION,'state':'intent','created':time.time(),
               'automatic_resubmit':False,'balance_before':balance,'request_record':relative(OUT/'generation-request.json')}
        save(OUT/'generation-intent.json',entry)
        bucket['tasks'][NAME]=entry
        save(LEDGER,data)
        response=await provider.request('POST','/generation/multiview-to-model',payload)
        task_id=response.get('task_id')
        if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',task_id):
            raise ProviderError('upstream_schema',uncertain=True)
        entry.update(task_id=task_id,state='submitted')
        save(LEDGER,data)
        save(OUT/'generation-task.json',{'task_id':task_id})
        plan.update(state='fullbody_generation_submitted',generation_request=relative(OUT/'generation-request.json'),
                    task_id=task_id,next_action='Poll the same task; no additional generation.')
        save(CHAR/'production-plan.json',plan)
        print(json.dumps({'state':'submitted','task_id':task_id,'variant':VARIANT,'estimate_credits':request['documented_estimate_credits'],'reservation':RESERVATION}));return
    if not entry or not entry.get('task_id'): raise ProviderError('no_submitted_task')
    task=await provider.task(entry['task_id'])
    status=task.get('status')
    safe={'task_id':entry['task_id'],'status':status,'progress':task.get('progress'),
          'credits_consumed':task.get('credits_consumed')}
    if status in ('success','failed','cancelled'):
        entry['state']=status
        if isinstance(task.get('credits_consumed'),(int,float)): entry['credits_consumed']=task['credits_consumed']
        save(LEDGER,data)
        safe.update(balance_before=entry['balance_before'],balance_after=await provider.balance())
        safe['balance_delta']=safe['balance_before']-safe['balance_after']
        if status=='success':
            if VARIANT=='hd':
                target=OUT/'model.glb'
                if not target.exists(): await quarantine_download(task.get('output',{}).get('model_url',''),target)
            else:
                existing=[OUT/('model.'+e) for e in ('glb','fbx','zip') if (OUT/('model.'+e)).exists()]
                target=existing[0] if existing else await download_native(task.get('output',{}).get('model_url',''))
            safe.update(file=relative(target),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
              imported_to_game=False,rigged=False,geometry_and_style_review='pending')
            plan.update(state='fullbody_mesh_awaiting_review',generated_3d=True,rigged=False,active_generation_variant=VARIANT,
              tripo_credits_consumed=entry.get('credits_consumed'),source_mesh=relative(target),
              next_action='Render and inspect the unchanged mesh in Blender; user review before replacements or rigging.')
            save(CHAR/'production-plan.json',plan)
        save(OUT/'generation-result.json',safe)
    else: save(OUT/'generation-status.json',safe)
    print(json.dumps(safe))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['submit','poll'])
    p.add_argument('--variant',choices=['hd','p2'],default='p2')
    args=p.parse_args();VARIANT=args.variant
    if VARIANT=='p2':
        OUT=CHAR/'03_generated_p2';NAME='explorer-fullbody-p2-v2';RESERVATION=150
    try:
        with single_batch(): asyncio.run(run(args.operation))
    except (ProviderError,ValueError) as e:
        print(json.dumps({'error':e.code if isinstance(e,ProviderError) else 'invalid_configuration',
                         'automatic_resubmit':False}));sys.exit(1)
