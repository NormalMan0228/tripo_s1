import asyncio,json,sys,time,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'tools')]
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
from generate_dev_character import upload
from generate_modular_character_parts import single_batch
import generate_fullbody_base as native
A=R/'art/characters/npc_cast_v1';LEDGER=R/'artifacts/character-hd-restart-20261004/budget.json';IDS=['sora','moru','naru','haeru']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
async def run(op):
 p=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
 for i,key in enumerate(IDS):
  out=A/key;name='npc_cast_v1_'+key;d=read(LEDGER);e=d['tasks'].get(name)
  if op=='submit':
   if e:
    if not e.get('task_id'):raise ProviderError('ambiguous_intent_no_resubmit')
    print(json.dumps({'character':key,'state':'existing_task','task_id':e['task_id']}),flush=True);continue
   committed=sum(float(t.get('credits_consumed',t['reservation'])) for t in d['tasks'].values());assert committed+150<=d['tripo_cap']
   balance=await p.balance();assert balance>=150
   plan=read(out/'production-plan.json');refs=plan['references'];tokens=[]
   for r in refs:
    f=R/r['file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'];tokens.append({r['view']:await upload(p,f)})
   payload={'inputs':tokens,'model':'P2-20260801','quad':False,'face_limit':20000,'texture':True,'pbr':True,'export_uv':True,'texture_version':'v3.5-20260815','texture_quality':'fast','delight':True,'texture_alignment':'original_image','orientation':'align_image','model_seed':2026100510+i,'texture_seed':2026100510+i}
   save(out/'request.json',{k:v for k,v in payload.items() if k!='inputs'}|{'references':refs,'user_authorization':'User explicitly selected integrated fullbody first on 2026-10-05','expected_credits':100,'reservation':150})
   e={'state':'intent','reservation':150,'expected_credits':100,'created':time.time(),'balance_before':balance,'automatic_resubmit':False};d['tasks'][name]=e;save(LEDGER,d);save(out/'intent.json',e)
   j=await p.request('POST','/generation/multiview-to-model',payload);tid=j.get('task_id');assert isinstance(tid,str);e.update(state='submitted',task_id=tid);save(LEDGER,d);save(out/'task.json',{'task_id':tid});print(json.dumps({'character':key,'status':'submitted','task_id':tid}),flush=True)
  else:
   if not e or not e.get('task_id'):continue
   t=await p.task(e['task_id']);s={'character':key,'task_id':e['task_id'],'status':t.get('status'),'progress':t.get('progress'),'credits_consumed':t.get('credits_consumed')}
   if s['status'] in ['success','failed','cancelled']:
    e['state']=s['status']
    if isinstance(s['credits_consumed'],(int,float)):e['credits_consumed']=s['credits_consumed']
    save(LEDGER,d)
    if s['status']=='success':
     existing=next((out/('model.'+ext) for ext in ['glb','fbx','zip'] if (out/('model.'+ext)).exists()),None);native.OUT=out;f=existing or await native.download_native(t.get('output',{}).get('model_url',''));s.update(file=f.relative_to(R).as_posix(),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),rigged=False)
    save(out/'result.json',s)
   else:save(out/'status.json',s)
   print(json.dumps(s),flush=True)
if __name__=='__main__':
 try:
  with single_batch():asyncio.run(run(sys.argv[1]))
 except Exception as e:print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
