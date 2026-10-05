"""Developer-only, separately budgeted Tripo experiments. Never prints secrets or signed URLs."""
import argparse, asyncio, json, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools'))
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from generate_dev_character import upload, quarantine_download
BASE=ROOT/'artifacts/detail-map-20261003'
LEDGER=BASE/'budget.json'
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def ledger():
 if not LEDGER.exists():
  save(LEDGER,{'date':'2026-10-03','tripo_balance_start':23110,'buckets':{x:{'tripo_cap':2000,'scenario_cap':1000,'tasks':{},'scenario':[]} for x in ['character_detail','village_map']}})
 return json.loads(LEDGER.read_text(encoding='utf-8'))
async def run(a):
 data=ledger();bucket=data['buckets'][a.bucket];out=BASE/'tripo'/a.bucket/a.name
 out.mkdir(parents=True,exist_ok=True)
 provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
 entry=bucket['tasks'].get(a.name)
 if not entry:
  committed=sum(float(t.get('credits_consumed',t['reservation'])) if isinstance(t.get('credits_consumed',t['reservation']),(int,float)) else t['reservation'] for t in bucket['tasks'].values())
  if committed+a.reserve>bucket['tripo_cap']:raise ProviderError('experiment_budget_exhausted')
  if await provider.balance()<a.reserve:raise ProviderError('insufficient_balance')
  entry={'reservation':a.reserve,'created':time.time(),'state':'intent','automatic_resubmit':False}
  bucket['tasks'][a.name]=entry;save(LEDGER,data)
  if a.mode=='segment':
   payload={'input':a.input_task,'model':'v2.0-20260430','segmentation_granularity':'detailed','split_by_connectivity':True};route='/mesh/segment'
  elif a.image:
   token=await upload(provider,a.image)
   payload={'input':token,'model':'P2-20260801','face_limit':a.faces,'texture':True,'pbr':True,'texture_quality':'detailed','orientation':'align_image'};route='/generation/image-to-model'
  else:
   payload={'prompt':a.prompt,'model':'P2-20260801','face_limit':a.faces,'texture':True,'pbr':True,'texture_quality':'detailed'};route='/generation/text-to-model'
  save(out/'request.json',{'route':route,**{k:v for k,v in payload.items() if k!='input'},'reference_file':str(a.image.relative_to(ROOT)) if a.image else None,'input_task':a.input_task})
  response=await provider.request('POST',route,payload)
  task_id=response.get('task_id')
  if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',task_id):raise ProviderError('upstream_schema')
  entry['task_id']=task_id;entry['state']='submitted';save(LEDGER,data)
 elif 'task_id' not in entry:
  raise ProviderError('ambiguous_intent_no_resubmit')
 if entry['state']=='success' and (out/'model.glb').exists():
  print(json.dumps({'name':a.name,'state':'already_completed','credits':entry.get('credits_consumed')}));return
 for _ in range(240):
  task=await provider.task(entry['task_id']);status=task.get('status')
  if status in ['success','failed','cancelled']:break
  await asyncio.sleep(5)
 else:raise ProviderError('task_still_running_resume_same_name')
 data=ledger();entry=data['buckets'][a.bucket]['tasks'][a.name]
 entry['state']=status
 if isinstance(task.get('credits_consumed'),(int,float)):entry['credits_consumed']=task['credits_consumed']
 save(LEDGER,data)
 if status=='success':
  await quarantine_download(task.get('output',{}).get('model_url',''),out/'model.glb')
 result={'name':a.name,'bucket':a.bucket,'task_id':entry['task_id'],'status':status,'credits_consumed':entry.get('credits_consumed'),'balance_after':await provider.balance()}
 save(out/'result.json',result);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bucket',choices=['character_detail','village_map'],required=True);p.add_argument('--name',required=True);p.add_argument('--reserve',type=int,default=250);p.add_argument('--mode',choices=['generate','segment'],default='generate');p.add_argument('--input-task');p.add_argument('--image',type=Path);p.add_argument('--prompt');p.add_argument('--faces',type=int,default=18000)
 a=p.parse_args()
 if not re.fullmatch(r'[a-z0-9-]{1,64}',a.name):p.error('invalid name')
 if a.reserve<=0 or a.reserve>2000:p.error('invalid reservation')
 if a.mode=='segment' and not a.input_task:p.error('input task required')
 if a.mode=='generate' and not (a.image or a.prompt):p.error('reference or prompt required')
 try:asyncio.run(run(a))
 except (ProviderError,ValueError) as e:print(json.dumps({'error':e.code if isinstance(e,ProviderError) else 'invalid_configuration','automatic_resubmit':False}));sys.exit(1)
