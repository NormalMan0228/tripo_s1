"""Two authorized image-reference experiments, isolated data, <=100 quoted credits.
No automatic resubmission after terminal/ambiguous state. No Blender.
"""
import asyncio,base64,hashlib,json,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings,read_tripo_key
from server.design_provider import DesignProvider
from server.provider import ProviderError
OUT=ROOT/'artifacts/picture-furniture-20261002'
BASE='Reproduce the supplied chest illustration: honey oak wood, sage green trim and flat lid, small brass front latch, ivory leaf emblem on the FRONT (+Z), four short rounded feet. No floor, background or other furniture. Overall width 1.2, depth .8, height .8 meters. '
CASES={'static':BASE+'Exactly ONE complete CLOSED static chest part. Empty animation program.',
 'dynamic':BASE+'Exactly TWO rigid parts named body and lid. Body is a genuinely hollow open-topped box WITHOUT ANY lid/cover/top panel: its part prompt must explicitly show the empty interior. Lid is ONLY a flat thin rectangular sage panel WITHOUT box, feet, front emblem or body. Body height .65, lid thickness .12; rear hinge lies on -Z. Choose body and lid positions/pivots so the closed lid sits flush on top. Click smoothly opens around local X to -95 degrees, click closes; set_open(x) numeric API sets desired open amount clamped 0..1 and returns it. No extra parts. Keep all operations within bounds.'}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
class PartBudget(DesignProvider):
    async def generate(self,prompt,*args,**kwargs):
        plan,program,meta=await super().generate(prompt,*args,**kwargs)
        expected=2 if 'Exactly TWO' in prompt else 1
        if len(plan['parts'])!=expected:raise ProviderError('experiment_part_count')
        return plan,program,meta

async def main():
    settings=Settings(data_dir=OUT/'server-data',mode='demo',studio_llm='codex',studio_design_format='classic',paid_enabled=True,daily_generation_limit=5,tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt'))
    app=create_app(settings,designer=PartBudget(settings),worker_enabled=False)
    image=(OUT/'reference.jpg').read_bytes()
    if len(image)>1024*1024:raise RuntimeError('image_too_large')
    save(OUT/'reference-spec.json',{'source':'Codex built-in imagegen, model not exposed by tool','source_concept':'variety-10/09-create-paint-summon.png, style only','source_file':'reference-source.png','transport_file':'reference.jpg','resolution':[1536,1024],'transport':'JPEG quality94, no crop/resize','sha256':hashlib.sha256(image).hexdigest()})
    if not (OUT/'balance-before.json').exists():save(OUT/'balance-before.json',{'balance':await app.state.studio.provider.balance()})
    with TestClient(app) as client:
        for kind,prompt in CASES.items():
            folder=OUT/kind;folder.mkdir(exist_ok=True);record=folder/'result.json'
            credentials={'username':'picture_'+kind,'password':'local-picture-experiment-only'}
            login=client.post('/v1/auth/register',json=credentials)
            if login.status_code!=200:login=client.post('/v1/auth/login',json=credentials)
            if login.status_code!=200:raise RuntimeError('experiment_login_failed')
            headers={'Authorization':'Bearer '+login.json()['token']}
            with app.state.db.transaction() as conn:
                user=conn.execute('SELECT id FROM users WHERE username=?',(credentials['username'],)).fetchone()[0]
                if not conn.execute("SELECT 1 FROM ledger WHERE user_id=? AND reason='picture_test_allowance'",(user,)).fetchone():
                    conn.execute('UPDATE users SET shards=shards+100 WHERE id=?',(user,))
                    conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),user,100,'picture_test_allowance',kind,time.time()))
            if record.exists():
                prior=json.loads(record.read_text());job=prior['id']
                if prior['state'] in ('ready','failed','unknown','cancelled'):continue
            else:
                request={'request_id':str(uuid.uuid4()),'prompt':prompt,'designer':'llm','geometry':'tripo','motion':kind,'material':'textured','image_mode':'original' if kind=='static' else 'refine','mesh_model':'v3.1-20260211','image':'data:image/jpeg;base64,'+base64.b64encode(image).decode(),'model':'gpt-6-luna','effort':'high'}
                safe={k:v for k,v in request.items() if k not in ('image','request_id')};safe.update(reference='../reference.jpg',face_limit=3000,quad=False,pbr=True,export_uv=True,image_refiner=None if kind=='static' else 'seedream_v5',refiner_size=None if kind=='static' else '2K')
                save(folder/'request-spec.json',safe)
                reply=client.post('/v1/studio/jobs',headers=headers,json=request)
                if reply.status_code!=200:raise RuntimeError('queue_failed_'+str(reply.status_code))
                job=reply.json()['id'];save(record,{'id':job,'state':'queued'})
            for _ in range(300):
                await app.state.studio.process(job)
                status=client.get('/v1/studio/jobs/'+job,headers=headers).json();save(record,status)
                if status['state']=='awaiting_confirmation':
                    expected=30 if kind=='static' else 70
                    if status['provenance']['estimated_tripo_credits']>expected:raise RuntimeError('quoted_budget_exceeded')
                    save(folder/'balance-before.json',{'balance':await app.state.studio.provider.balance()})
                    reply=client.post('/v1/studio/jobs/'+job+'/confirm',headers=headers,json={'request_id':str(uuid.uuid4())})
                    if reply.status_code!=200:raise RuntimeError('confirmation_failed')
                    print(json.dumps({'case':kind,'state':'confirmed','quoted_credits':expected}),flush=True)
                elif status['state'] in ('ready','failed','unknown','cancelled'):
                    after=await app.state.studio.provider.balance();save(folder/'balance-after.json',{'balance':after});save(OUT/'balance-after.json',{'balance':after})
                    print(json.dumps({'case':kind,'state':status['state'],'error':status.get('error'),'known_credits':status['provenance'].get('known_tripo_credits')}),flush=True)
                    if status['state']=='ready':
                        assembly=client.get('/v1/objects/'+status['object_id']+'/assembly',headers=headers).json();save(folder/'assembly.json',assembly)
                    else:return
                    break
                await asyncio.sleep(5)
            else:print('Polling paused; recorded task may be resumed without new submission.');return
    print('PICTURE_EXPERIMENT_COMPLETE',flush=True)
if __name__=='__main__':
    try:asyncio.run(main())
    except ProviderError as error:print(json.dumps({'error':error.code,'automatic_resubmit':False}));sys.exit(1)
