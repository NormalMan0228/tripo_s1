"""Retrieve the approved P2 face's materials in portable GLTF; preserve original quad FBX."""
import argparse,asyncio,hashlib,json,re,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'tools')]
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_hd_character_restart import save
from generate_modular_character_parts import single_batch
import generate_fullbody_base as native
O=R/'art/characters/explorer_b_integrated_face_haircards_v1/head/texture_payload'
L=R/'artifacts/character-hd-restart-20261004/budget.json';NAME='integrated_face_haircards_v1_head_export_gltf'
INPUT_TASK='38676a32-c0e8-4ccf-b30f-bc3b0fdb2af0'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
async def run(op):
 O.mkdir(parents=True,exist_ok=True);d=read(L);entry=d['tasks'].get(NAME)
 provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
 if op=='submit':
  if entry or (O/'generation-intent.json').exists():
   if not entry or not entry.get('task_id'):raise ProviderError('ambiguous_intent_no_resubmit')
   print(json.dumps({'task_id':entry['task_id'],'state':'existing_task_preserved'}));return
  committed=sum(float(t.get('credits_consumed',t['reservation'])) for t in d['tasks'].values())
  if committed+10>d['tripo_cap']:raise ProviderError('budget_exhausted')
  before=await provider.balance()
  if before<10:raise ProviderError('insufficient_balance')
  payload={'input':INPUT_TASK,'format':'GLTF','bake':False,'pack_uv':False}
  save(O/'generation-request.json',{**payload,'route':'/models/convert','reservation':10,'expected_credits':5,'reason':'Quad FBX download refers to unavailable external textures; retrieve embedded materials without regenerating face, UV packing, retopology or changing the original FBX. Within newly approved cap 2000.','source':'https://developers.tripo3d.ai/en/docs/models-convert','automatic_resubmit':False})
  entry={'state':'intent','reservation':10,'expected_credits':5,'created':time.time(),'balance_before':before,'automatic_resubmit':False}
  save(O/'generation-intent.json',entry);d['tasks'][NAME]=entry;save(L,d)
  result=await provider.request('POST','/models/convert',payload);tid=result.get('task_id')
  if not isinstance(tid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',tid):raise ProviderError('upstream_schema',uncertain=True)
  entry.update(state='submitted',task_id=tid);save(L,d);save(O/'generation-task.json',{'task_id':tid});print(json.dumps({'submitted':tid}));return
 if not entry or not entry.get('task_id'):raise ProviderError('no_task')
 task=await provider.task(entry['task_id']);safe={k:task.get(k) for k in ['status','progress','credits_consumed']};safe['task_id']=entry['task_id']
 if safe['status'] in ['success','failed','cancelled']:
  entry['state']=safe['status']
  if isinstance(safe['credits_consumed'],(int,float)):entry['credits_consumed']=safe['credits_consumed']
  save(L,d)
  if safe['status']=='success':
   native.OUT=O;files=[O/('model.'+x) for x in ['glb','zip'] if (O/('model.'+x)).exists()]
   f=files[0] if files else await native.download_native(task['output']['model_url'])
   safe.update(file=f.relative_to(R).as_posix(),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size)
  save(O/'generation-result.json',safe)
 else:save(O/'generation-status.json',safe)
 print(json.dumps(safe))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['submit','poll']);a=p.parse_args()
 try:
  with single_batch():asyncio.run(run(a.operation))
 except Exception as e:print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
