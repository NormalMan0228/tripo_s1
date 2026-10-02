"""Measure the shipping provider's extended gate and bounded repair policy."""
import argparse,asyncio,base64,json,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import Settings
from server.design_provider import DesignProvider
from server.asset_contract import prompt_for
from server.structured_design import prompt_for_structured
from tools.benchmark_assets import CASES,check_behavior

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--models',nargs='+',default=['gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra'])
    parser.add_argument('--efforts',nargs='+',default=['medium','high'])
    parser.add_argument('--cases',nargs='+',choices=list(CASES),default=['chest','flower','clock'])
    parser.add_argument('--reference-suite',action='store_true')
    parser.add_argument('--format',choices=['classic','structured'],default='classic')
    parser.add_argument('--experiment',default=None,help='Distinct cohort label when testing a revised repair policy')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(exist_ok=True)
    provider=DesignProvider(Settings(mode='demo',studio_llm='codex',studio_design_format=args.format))
    references={'static_vase':'reference-0.png','windmill':'reference-1.png','chest':'reference-5.png'}
    if args.reference_suite:
        args.cases=['static_vase','windmill','chest']
        (out/'references').mkdir(exist_ok=True)
        for case,filename in references.items():shutil.copy2(ROOT/'artifacts/furniture-review-frames'/filename,out/'references'/(case+'.png'))
    for effort in args.efforts:
        for model in args.models:
            for case in args.cases:
                if (out/'STOP').exists():return
                dest=out/(model+'_'+effort+'_'+case);dest.mkdir(exist_ok=True)
                if (dest/'result.json').exists():continue
                prompt=CASES[case];image=None
                if args.reference_suite:
                    prompt+='\nUse the attached game-rendered reference for the object silhouette and material colors. Ignore the floor, background and shadows. The movement and part-count instructions above take precedence. Reconstruct a closed/rest pose for the initial design; preserve the reference identity in each standalone part prompt.'
                    image='data:image/png;base64,'+base64.b64encode((out/'references'/(case+'.png')).read_bytes()).decode()
                (dest/'prompt.txt').write_text((prompt_for_structured if args.format=='structured' else prompt_for)(prompt),encoding='utf-8')
                result={'model':model,'effort':effort,'case':case,'billing':'Codex subscription; not API charge','experiment':'publication_v2_one_repair'}
                if args.reference_suite:result['experiment']='image_reference_publication_v2'
                elif args.format=='structured':result['experiment']='structured_publication_v2'
                if args.experiment:result['experiment']=args.experiment
                result['design_format']=args.format
                start=time.monotonic()
                try:
                    plan,program,meta=await provider.generate(prompt,model,effort,image)
                    result.update(status='validated',usage=meta['usage'],attempts=meta['attempts'],validation=meta['validation'],behavior=check_behavior(plan,program,case))
                    (dest/'output.json').write_text(json.dumps({'plan':plan,'program':program},ensure_ascii=False,indent=2),encoding='utf-8')
                except Exception as error:
                    result.update(status='invalid_design',validation_error=type(error).__name__+': '+str(error)[:250])
                    if hasattr(error,'usage'):result.update(usage=error.usage,attempts=error.attempts)
                result['seconds']=round(time.monotonic()-start,2)
                (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({k:result.get(k) for k in ('model','effort','case','status','seconds','validation_error')}),flush=True)
if __name__=='__main__':asyncio.run(main())
