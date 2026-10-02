"""Schema-constrained Codex experiment; separate cohort from classic prompting."""
import argparse,asyncio,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import Settings
from server.design_provider import DesignProvider
from server.structured_design import SCHEMA,prompt_for_structured,canonical
from server.asset_contract import parse_design
from tools.benchmark_assets import CASES,check_behavior

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--models',nargs='+',default=['gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra'])
    parser.add_argument('--efforts',nargs='+',default=['medium','high'])
    parser.add_argument('--cases',nargs='+',choices=list(CASES),default=['chest','flower','clock']);args=parser.parse_args()
    out=args.out.resolve();out.mkdir(exist_ok=True);(out/'schema.json').write_text(json.dumps(SCHEMA,indent=2),encoding='utf-8')
    provider=DesignProvider(Settings(mode='demo',studio_llm='codex',studio_design_format='structured'))
    for effort in args.efforts:
        for model in args.models:
            for case in args.cases:
                if (out/'STOP').exists():return
                dest=out/(model+'_'+effort+'_'+case);dest.mkdir(exist_ok=True)
                if (dest/'result.json').exists():continue
                (dest/'prompt.txt').write_text(prompt_for_structured(CASES[case]),encoding='utf-8')
                result={'model':model,'effort':effort,'case':case,'billing':'Codex subscription; not API charge','experiment':'structured_wire_format'}
                start=time.monotonic()
                try:
                    raw,usage=await provider._codex(CASES[case],model,effort,None,'')
                    result['usage']=usage;(dest/'wire-output.json').write_text(raw,encoding='utf-8')
                    encoded=canonical(raw);(dest/'output.json').write_text(encoded,encoding='utf-8')
                    plan,program,report=parse_design(encoded)
                    result.update(status='validated',validation=report,behavior=check_behavior(plan,program,case))
                except Exception as exc:result.update(status='invalid_design',validation_error=type(exc).__name__+': '+str(exc)[:250])
                result['seconds']=round(time.monotonic()-start,2)
                (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({k:result.get(k) for k in ('model','effort','case','status','seconds','validation_error')},ensure_ascii=True),flush=True)

if __name__=='__main__':asyncio.run(main())
