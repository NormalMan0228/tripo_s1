"""Approved front + side P2 face task, resumable and guarded by the existing ledger."""
import argparse,asyncio,hashlib,json,re,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'tools')]
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_dev_character import upload
from generate_modular_character_parts import single_batch
from generate_hd_character_restart import save
import generate_fullbody_base as native
O=R/'art/characters/explorer_b_face_multiview_meshhair_v2/head';REF=R/'art/references/explorer_b_face_multiview_meshhair_v2';LEDGER=R/'artifacts/character-hd-restart-20261004/budget.json';NAME='face_multiview_meshhair_v2_head'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
async def run(operation):
 O.mkdir(parents=True,exist_ok=True);ledger=read(LEDGER);entry=ledger['tasks'].get(NAME);provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
 if operation=='submit':
  if entry or (O/'generation-intent.json').exists():
   if not entry or not entry.get('task_id'):raise ProviderError('ambiguous_intent_no_resubmit')
   print(json.dumps({'status':'existing_task_preserved','task_id':entry['task_id']}));return
  plan=read(O/'production-plan.json')
  if not plan.get('reference_approved'):raise ProviderError('reference_not_approved')
  refs=[(v,REF/f) for v,f in [('front','01_head_front.png'),('left','02_head_left.png'),('right','03_head_right.png')]]
  for v,p in refs:
   if hashlib.sha256(p.read_bytes()).hexdigest()!=plan['reference_sha256_by_view'][v]:raise ProviderError('approved_reference_changed')
  committed=sum(float(t.get('credits_consumed',t['reservation'])) for t in ledger['tasks'].values())
  if committed+150>ledger['tripo_cap']:raise ProviderError('budget_exhausted')
  balance=await provider.balance()
  if balance<150:raise ProviderError('insufficient_balance')
  payload={'model':'P2-20260801','quad':True,'face_limit':20000,'texture':True,'pbr':True,'export_uv':True,'texture_quality':'detailed','texture_version':'v3.5-20260815','delight':True,'texture_alignment':'original_image','orientation':'align_image','model_seed':2026100562,'texture_seed':2026100562}
  request={**payload,'route':'/generation/multiview-to-model','references':[{'view':v,'path':p.relative_to(R).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for v,p in refs],'reservation':150,'expected_credits':120,'user_authorization':plan['user_authorization'],'automatic_resubmit':False}
  save(O/'generation-request.json',request)
  tokens=[(v,await upload(provider,p)) for v,p in refs];payload['inputs']=[{v:token} for v,token in tokens]
  entry={'state':'intent','reservation':150,'expected_credits':120,'created':time.time(),'balance_before':balance,'request_record':(O/'generation-request.json').relative_to(R).as_posix(),'automatic_resubmit':False}
  save(O/'generation-intent.json',entry);ledger['tasks'][NAME]=entry;save(LEDGER,ledger)
  result=await provider.request('POST','/generation/multiview-to-model',payload);tid=result.get('task_id')
  if not isinstance(tid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',tid):raise ProviderError('upstream_schema',uncertain=True)
  entry.update(state='submitted',task_id=tid);save(LEDGER,ledger);save(O/'generation-task.json',{'task_id':tid});print(json.dumps({'status':'submitted','task_id':tid,'views':['front','left','right'],'expected_credits':120}));return
 if not entry or not entry.get('task_id'):raise ProviderError('no_task')
 task=await provider.task(entry['task_id']);safe={'task_id':entry['task_id'],'status':task.get('status'),'progress':task.get('progress'),'credits_consumed':task.get('credits_consumed')}
 if safe['status'] in ('success','failed','cancelled'):
  entry['state']=safe['status']
  if isinstance(safe['credits_consumed'],(int,float)):entry['credits_consumed']=safe['credits_consumed']
  save(LEDGER,ledger);safe['budget_remaining']=ledger['tripo_cap']-sum(float(t.get('credits_consumed',t['reservation'])) for t in ledger['tasks'].values())
  if safe['status']=='success':
   existing=next((O/('model.'+ext) for ext in ['fbx','glb','zip'] if (O/('model.'+ext)).exists()),None)
   native.OUT=O;file=existing or await native.download_native(task.get('output',{}).get('model_url',''))
   safe.update(file=file.relative_to(R).as_posix(),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),rigged=False,views=['front','left','right']);save(O/'generation-result.json',safe)
  save(O/'generation-status.json',safe)
 else:save(O/'generation-status.json',safe)
 print(json.dumps(safe))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['submit','poll']);a=p.parse_args()
 try:
  with single_batch():asyncio.run(run(a.operation))
 except Exception as e:print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
