"""Authorized operator experiment, isolated DB: image+local LLM -> image refinement -> H3.
Maximum one part, estimate <=25 credits. Known tasks are resumed; ambiguous tasks stop.
Run separately from other credit-measurement experiments so balance deltas stay attributable.
"""
import argparse,asyncio,base64,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings,read_tripo_key
from server.design_provider import DesignProvider
from server.provider import ProviderError
OUT=ROOT/'artifacts/reference-chain'

class SinglePartDesigner(DesignProvider):
    async def generate(self,*args,**kwargs):
        plan,program,meta=await super().generate(*args,**kwargs)
        if len(plan['parts'])!=1:raise ProviderError('experiment_part_limit')
        return plan,program,meta

async def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--prompt',default='Make a static ceramic vase based on the supplied image. Keep its rounded body and small neck. Use a pale ivory surface and a soft sage leaf motif. Exactly ONE complete part, no animation, no pedestal or floor.')
    args=parser.parse_args();OUT=args.out.resolve()
    OUT.mkdir(exist_ok=True,parents=True);record=OUT/'result.json'
    settings=Settings(data_dir=OUT/'server-data',studio_llm='codex',paid_enabled=True,tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt'))
    app=create_app(settings,designer=SinglePartDesigner(settings),worker_enabled=False)
    with TestClient(app) as client:
        credentials={'username':'reference_qa','password':'Local-reference-qa-password'}
        reply=client.post('/v1/auth/register',json=credentials)
        if reply.status_code!=200:reply=client.post('/v1/auth/login',json=credentials)
        if reply.status_code!=200:raise RuntimeError('experiment_login_failed')
        headers={'Authorization':'Bearer '+reply.json()['token']}
        if record.exists():
            saved=json.loads(record.read_text());job=saved['job_id']
            if saved['state'] in ('ready','failed','unknown','cancelled'):print(json.dumps({'state':saved['state'],'new_api_calls':0}));return
        else:
            blob=args.image.read_bytes()
            if len(blob)>1024*1024:raise RuntimeError('reference_too_large')
            request={'request_id':str(uuid.uuid4()),'prompt':args.prompt,
                'designer':'llm','geometry':'tripo','motion':'static','material':'mesh','image_mode':'refine','mesh_model':'v3.1-20260211','image':'data:image/png;base64,'+base64.b64encode(blob).decode(),'model':'gpt-6-luna','effort':'medium'}
            reply=client.post('/v1/studio/jobs',headers=headers,json=request)
            if reply.status_code!=200:raise RuntimeError('experiment_queue_failed')
            job=reply.json()['id'];record.write_text(json.dumps({'job_id':job,'state':'queued'}))
        for _ in range(240):
            await app.state.studio.process(job)
            status=client.get('/v1/studio/jobs/'+job,headers=headers).json()
            record.write_text(json.dumps({'job_id':job,**status},indent=2),encoding='utf-8')
            if status['state']=='awaiting_confirmation':
                quote=status['provenance']['estimated_tripo_credits']
                if quote>25:raise RuntimeError('experiment_cost_limit')
                (OUT/'balance-before.json').write_text(json.dumps({'balance':await app.state.studio.provider.balance()}))
                reply=client.post('/v1/studio/jobs/'+job+'/confirm',headers=headers,json={'request_id':str(uuid.uuid4())})
                if reply.status_code!=200:raise RuntimeError('experiment_confirmation_failed')
            elif status['state'] in ('ready','failed','unknown','cancelled'):
                print(json.dumps({'state':status['state'],'error':status.get('error'),'provenance':status['provenance']}),flush=True)
                (OUT/'balance-after.json').write_text(json.dumps({'balance':await app.state.studio.provider.balance()}))
                if status['state']=='ready':
                    assembly=client.get('/v1/objects/'+status['object_id']+'/assembly',headers=headers).json()
                    (OUT/'assembly.json').write_text(json.dumps(assembly,indent=2),encoding='utf-8')
                return
            await asyncio.sleep(5)
        print('Known task retained for later polling; no new submission.')
if __name__=='__main__':asyncio.run(main())
