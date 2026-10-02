"""Operator-only, resumable Tripo character experiment. Never retargets animation.

Credentials stay in the user's server-local file, never in output or artifacts.
Each paid operation has an exclusive intent file: ambiguous requests are not retried.
"""
import argparse, json, sys, time
from pathlib import Path
from urllib.parse import urlparse
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.config import read_tripo_key

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/characters/explorer-b-v1'
BASE='https://openapi.tripo3d.ai/v3'

def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['generate','rigcheck','rig','poll','download','balance'])
    p.add_argument('--stage',default='generate',choices=['generate','rigcheck','rig'])
    p.add_argument('--key-file',type=Path,required=True)
    args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    key=read_tripo_key(args.key_file)
    with httpx.Client(timeout=90,follow_redirects=False,headers={'Authorization':'Bearer '+key}) as c:
        def request(method,route,**kw):
            r=c.request(method,BASE+route,**kw)
            if r.status_code!=200: raise RuntimeError('http_'+str(r.status_code))
            if 'application/json' not in r.headers.get('content-type',''): raise RuntimeError('non_json')
            d=r.json()
            if d.get('code')!=0: raise RuntimeError('provider_code_'+str(d.get('code')))
            return d['data']
        if args.operation=='balance':
            d=request('GET','/account/balance')
            safe={k:d.get(k) for k in ('balance','frozen')}
            save('balance-latest.json',safe);print(json.dumps(safe));return
        stage=args.operation if args.operation in ('generate','rigcheck','rig') else args.stage
        taskfile=OUT/(stage+'-task.json')
        if args.operation in ('generate','rigcheck','rig'):
            if taskfile.exists(): print('Existing task retained; use poll.');return
            intent=OUT/(stage+'-intent.json')
            with intent.open('x',encoding='utf-8') as f: json.dump({'submitted_at':time.time(),'operation':stage},f)
            balance=request('GET','/account/balance')
            save(stage+'-balance-before.json',{k:balance.get(k) for k in ('balance','frozen')})
            if balance['balance']<200: raise RuntimeError('insufficient_experiment_budget')
            if stage=='generate':
                with (OUT/'reference.png').open('rb') as f:
                    upload=request('POST','/files',files={'file':('reference.png',f,'image/png')})
                payload={'input':upload['file_token'],'model':'P2-20260801','face_limit':16000,'texture':True,'pbr':True,'texture_quality':'standard','quad':False,'export_uv':True}
                route='/generation/image-to-model'
            else:
                src=json.loads((OUT/'generate-task.json').read_text())['task_id']
                payload={'input':src}
                route='/animations/rig-check'
                if stage=='rig':
                    payload.update(model='v1.0-20240301',rig_type='biped',spec='tripo',out_format='glb')
                    route='/animations/rig'
            save(stage+'-request.json',payload)
            d=request('POST',route,json=payload)
            save(stage+'-task.json',{'task_id':d['task_id']})
            print(json.dumps({'stage':stage,'submitted':True,'task_id':d['task_id']}));return
        task=json.loads(taskfile.read_text())['task_id']
        if not isinstance(task,str) or '/' in task: raise RuntimeError('invalid_task_id')
        d=request('GET','/tasks/'+task)
        safe={k:d.get(k) for k in ('task_id','status','progress','credits_consumed','error_code') if k in d}
        safe['output_fields']=list(d.get('output',{}))
        for k,v in d.get('output',{}).items():
            if isinstance(v,(bool,int,float)): safe[k]=v
        save(stage+'-status.json',safe)
        print(json.dumps(safe))
        if args.operation=='download':
            if d.get('status')!='success':raise RuntimeError('task_not_complete')
            output=d.get('output',{});url=output.get('model_url') or output.get('model')
            if not isinstance(url,str):raise RuntimeError('missing_model_url')
            u=urlparse(url)
            if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or not (u.hostname=='tripo-data.rg1.data.tripo3d.com' or u.hostname=='tripo3d.ai' or (u.hostname or '').endswith('.tripo3d.ai')): raise RuntimeError('unapproved_download_host')
            # Deliberately independent client: no API Authorization sent to asset CDN.
            with httpx.Client(timeout=120,follow_redirects=False) as dl:
                with dl.stream('GET',url) as response:
                    if response.status_code!=200:raise RuntimeError('download_http_'+str(response.status_code))
                    blob=bytearray()
                    for part in response.iter_bytes():
                        blob.extend(part)
                        if len(blob)>150*1024*1024:raise RuntimeError('asset_too_large')
            if blob[:4]!=b'glTF':raise RuntimeError('not_glb')
            dest=OUT/(stage+'-original.glb');dest.write_bytes(blob)
            print(json.dumps({'saved':dest.name,'bytes':len(blob)}))

if __name__=='__main__':
    try:main()
    except Exception as e:
        # Never print raw upstream bodies, headers, credentials or signed URLs.
        allowed=('http_','provider_code_','non_json','insufficient_','invalid_','task_','missing_','unapproved_','download_','asset_','not_glb')
        label=str(e) if isinstance(e,RuntimeError) and str(e).startswith(allowed) else type(e).__name__
        print(json.dumps({'error':label,'automatic_resubmit':False}));sys.exit(1)
