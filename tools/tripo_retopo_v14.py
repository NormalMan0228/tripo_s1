import asyncio,json,sys,time,hashlib,httpx
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'tools')]
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_modular_character_parts import single_batch
import generate_fullbody_base as native
A=R/'art/characters/explorer_b_tripo_retopo_v14';LEDGER=R/'artifacts/character-hd-restart-20261004/budget.json';NAME='face_smart_retopology_v14'
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
async def run(op):
 p=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')));d=json.loads(LEDGER.read_text(encoding='utf-8-sig'));e=d['tasks'].get(NAME)
 if op=='submit':
  if e:
   print(json.dumps({'state':e['state'],'task_id':e.get('task_id'),'resubmit':False}));return
  committed=sum(float(t.get('credits_consumed',t['reservation'])) for t in d['tasks'].values());assert committed+30<=d['tripo_cap']
  balance=await p.balance();assert balance>=30
  blob=(A/'face_input.glb').read_bytes()
  async with httpx.AsyncClient(timeout=90,follow_redirects=False) as c:
   r=await c.post(p.BASE+'/files',headers={'Authorization':'Bearer '+p.settings.tripo_key},files={'file':('face_input.glb',blob,'model/gltf-binary')})
  j=r.json();token=j.get('data',{}).get('file_token');assert j.get('code')==0 and isinstance(token,str)
  request={'input':token,'model':'v2.0','face_limit':8000,'quad':True,'bake':True}
  save(A/'request.json',{k:v for k,v in request.items() if k!='input'}|{'source':'face_input.glb','source_sha256':hashlib.sha256(blob).hexdigest(),'docs':'https://developers.tripo3d.ai/en/docs/mesh-decimate','authorized':'User requested Tripo retopology of current model','expected_credits':30})
  e={'state':'intent','created':time.time(),'reservation':30,'balance_before':balance,'automatic_resubmit':False};d['tasks'][NAME]=e;save(LEDGER,d);save(A/'intent.json',e)
  j=await p.request('POST','/mesh/decimate',request);tid=j.get('task_id');assert isinstance(tid,str)
  e.update(state='submitted',task_id=tid);save(LEDGER,d);save(A/'task.json',{'task_id':tid});print(json.dumps({'status':'submitted','task_id':tid}));return
 assert e and e.get('task_id')
 t=await p.task(e['task_id']);safe={k:t.get(k) for k in ['status','progress','credits_consumed']};safe['task_id']=e['task_id']
 if safe['status'] in ['success','failed','cancelled']:
  e['state']=safe['status']
  if isinstance(safe['credits_consumed'],(int,float)):e['credits_consumed']=safe['credits_consumed']
  save(LEDGER,d)
  if safe['status']=='success':
   native.OUT=A
   files=list(A.glob('model.*'));f=files[0] if files else await native.download_native(t.get('output',{}).get('model_url',''))
   safe.update(file=str(f.relative_to(R)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size)
  safe['budget_remaining']=d['tripo_cap']-sum(float(t.get('credits_consumed',t['reservation'])) for t in d['tasks'].values())
  save(A/'result.json',safe)
 else:save(A/'status.json',safe)
 print(json.dumps(safe))
if __name__=='__main__':
 try:
  with single_batch():asyncio.run(run(sys.argv[1]))
 except Exception as e:print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
