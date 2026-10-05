"""Operator experiment: local Codex design -> real Tripo -> private workshop DB.
At most 3 parts per case; stops before paid generation if that budget is exceeded.
"""
import asyncio,json,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings,read_tripo_key
from server.design_provider import DesignProvider
from server.provider import ProviderError
OUT=ROOT/'artifacts/live-studio-test'

class BudgetedDesigner(DesignProvider):
    async def generate(self,*args,**kwargs):
        plan,program,provenance=await super().generate(*args,**kwargs)
        if len(plan['parts'])>3:raise ProviderError('experiment_part_budget_exceeded')
        return plan,program,provenance

async def main():
    OUT.mkdir(exist_ok=True)
    settings=Settings(data_dir=ROOT/'artifacts/studio-review-data',studio_llm='codex',tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt'),paid_enabled=True,daily_generation_limit=100)
    app=create_app(settings,designer=BudgetedDesigner(settings),worker_enabled=False)
    with TestClient(app) as c:
        login=c.post('/v1/auth/login',json={'username':'workshop','password':'Tripothon-local-demo'})
        if login.status_code!=200:raise RuntimeError('login_failed')
        headers={'Authorization':'Bearer '+login.json()['token']}
        cases=[('static','A cozy sage ceramic vase with a rounded belly and short neck. Exactly ONE static part, no moving features.'),
               ('dynamic','A cozy miniature windmill decoration. Exactly TWO parts: a stationary wooden base/tower and a separate four-blade rotor. Rotor faces +Z, centered at [0,1.1,0.25], radius .45 meters. Rotate the rotor smoothly around local Z at 30 degrees/second. Clicking toggles pause, and clicking again resumes without jumping. Generate a reusable rotor_angle API. Wrap angles to -180..180. No other parts.')]
        for kind,prompt in cases:
            record=OUT/(kind+'.json')
            if record.exists():
                status=json.loads(record.read_text());job_id=status['job_id']
                if status.get('state') in ('ready','failed','unknown'):continue
            else:
                payload={'request_id':str(uuid.uuid4()),'prompt':prompt,'designer':'llm','geometry':'tripo','material':'mesh','motion':kind,'model':'gpt-6-luna','effort':'medium'}
                result=c.post('/v1/studio/jobs',headers=headers,json=payload)
                if result.status_code!=200:raise RuntimeError('queue_failed_'+str(result.status_code))
                job_id=result.json()['id'];record.write_text(json.dumps({'job_id':job_id,'state':'queued'}))
            for _ in range(240):
                await app.state.studio.process(job_id)
                result=c.get('/v1/studio/jobs/'+job_id,headers=headers).json()
                record.write_text(json.dumps({'job_id':job_id,**result},indent=2),encoding='utf-8')
                if result['state'] in ('ready','failed','unknown'):
                    print(json.dumps({'case':kind,'state':result['state'],'error':result.get('error'),'provenance':result.get('provenance')}),flush=True);break
                await asyncio.sleep(5)
            if result['state']=='ready':
                manifest=c.get('/v1/objects/'+result['object_id']+'/assembly',headers=headers).json()
                (OUT/(kind+'-assembly.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
                # Allow review without changing the player's world; these are local test objects.
                print('Published private assembly; ready for Godot review.',flush=True)
if __name__=='__main__':asyncio.run(main())
