"""Six bounded, operator-authorized Tripo calls: static vs two-part hinged chest.
No Blender. Intent-before-submit, resumable polling, no ambiguous resubmission.
"""
import argparse,asyncio,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
OUT=ROOT/'artifacts/furniture/runtime-comparison'
STYLE='Cozy storybook village game furniture, rounded honey oak timber, hand crafted joinery, matte surfaces, sage green trim, medium detail, clean topology, isolated centered object, no ground, no text. '
PROMPTS={
 'static':'A complete CLOSED wooden storage chest with flat hinged lid, small brass latch and four short feet. Aspect ratio width 1.2 height .8 depth .8. ',
 'body':'Only the open-topped BODY of a wooden storage chest, a hollow rectangular wooden box with four short feet and a small brass latch on FRONT (+Z). NO lid, no cover, no hinge above the rim. Width 1.2 height .65 depth .8. ',
 'lid':'Only a flat rectangular wooden chest LID panel with soft rounded corners and subtle wood trim. NO box, no base, no legs, no handle. Width 1.2 height .12 depth .8. '
}
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT);parser.add_argument('--model',default='P2-20260801');parser.add_argument('--max-per-task-credits',type=float,default=120);args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    settings=Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt'),tripo_model=args.model)
    provider=TripoProvider(settings)
    for material in ['mesh','textured']:
        for kind in ['static','body','lid']:
            folder=out/(kind+'-'+material);folder.mkdir(exist_ok=True)
            if (folder/'result.json').exists():continue
            taskfile=folder/'task.json';intent=folder/'intent.json'
            if not taskfile.exists():
                if intent.exists():print('Ambiguous intent; operator reconciliation required.',flush=True);return
                before=await provider.balance()
                if before<500:raise ProviderError('experiment_budget_low')
                save(folder/'balance-before.json',{'balance':before})
                payload={'model':settings.tripo_model,'prompt':STYLE+PROMPTS[kind],
                    'face_limit':3000,'quad':False,'texture':material=='textured','pbr':material=='textured','export_uv':material=='textured'}
                save(folder/'request.json',payload)
                with intent.open('x',encoding='utf-8') as f:json.dump({'time':time.time(),'automatic_resubmit':False},f)
                result=await provider.request('POST','/generation/text-to-model',payload)
                save(taskfile,{'task_id':result['task_id']})
            task=json.loads(taskfile.read_text())['task_id']
            for _ in range(240):
                result=await provider.task(task)
                status=result.get('status')
                if status in ('success','failed','cancelled'):break
                await asyncio.sleep(5)
            safe={k:result[k] for k in ('status','credits_consumed','error_code') if k in result}
            safe.update(kind=kind,material=material,model=settings.tripo_model)
            safe['balance_before']=json.loads((folder/'balance-before.json').read_text())['balance']
            safe['balance_after']=await provider.balance()
            safe['balance_delta']=safe['balance_before']-safe['balance_after']
            if status=='success':
                try:
                    blob=await provider.download(result.get('output',{}).get('model_url',''),allow_textures=material=='textured')
                    (folder/'model.glb').write_bytes(blob);safe['validated']=True;safe['bytes']=len(blob)
                except ProviderError as exc:safe.update(validated=False,validation_error=exc.code)
            save(folder/'result.json',safe)
            print(json.dumps(safe),flush=True)
            if (safe.get('credits_consumed') or safe['balance_delta'])>args.max_per_task_credits:
                print('Observed task cost exceeded experiment expectation; stopping before any further submission.',flush=True);return
            if status not in ('success','failed','cancelled'):return
if __name__=='__main__':
    try:asyncio.run(main())
    except ProviderError as exc:print(json.dumps({'error':exc.code,'automatic_resubmit':False}));sys.exit(1)
