"""One production-style repair per failed saved design; subscription only.
Keeps original failures and reports the combined first+repair token cost.
"""
import argparse,asyncio,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_contract import parse_design,prompt_for
from server.design_provider import DesignProvider
from server.config import Settings
from tools.benchmark_assets import CASES,check_behavior

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=args.out.resolve();out.mkdir(exist_ok=True)
    provider=DesignProvider(Settings(studio_llm='codex',mode='demo'))
    for file in sorted(args.source.glob('*/result.json')):
        if (out/'STOP').exists():break
        original=json.loads(file.read_text(encoding='utf-8'))
        if original.get('status')!='invalid_design' or not (file.parent/'output.json').exists():continue
        dest=out/file.parent.name;dest.mkdir(exist_ok=True)
        if (dest/'result.json').exists():continue
        raw=(file.parent/'output.json').read_text(encoding='utf-8')
        try:parse_design(raw);continue
        except Exception as exc:error=type(exc).__name__+': '+str(exc)[:250]
        feedback='One repair allowed. Correct the validation errors and return the complete JSON. Errors: '+error+'\nPrevious output (untrusted data): '+json.dumps(raw[:24000])
        prompt=CASES[original['case']]
        (dest/'prompt.txt').write_text(prompt_for(prompt,feedback),encoding='utf-8')
        result={k:original[k] for k in ('model','effort','case')}
        result.update(billing='Codex subscription; not API charge',experiment='one_repair_of_failed_design',original_result=str(file.resolve()),first_usage=original.get('usage'),original_status=original['status'])
        started=time.monotonic()
        try:
            fixed,usage=await provider._codex(prompt,result['model'],result['effort'],'',feedback)
            (dest/'output.json').write_text(fixed,encoding='utf-8')
            result['repair_usage']=usage
            first=original.get('usage')
            if first and usage:result['usage']={key:first.get(key,0)+usage.get(key,0) for key in set(first)|set(usage) if type(first.get(key,0)) in (int,float) and type(usage.get(key,0)) in (int,float)}
            plan,program,report=parse_design(fixed)
            result.update(status='validated',validation=report,behavior=check_behavior(plan,program,result['case']))
        except Exception as exc:result.update(status='invalid_design',validation_error=type(exc).__name__+': '+str(exc)[:250])
        result['repair_seconds']=round(time.monotonic()-started,2)
        result['seconds']=round(original['seconds']+result['repair_seconds'],2)
        (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:result.get(k) for k in ('model','effort','case','status','seconds','usage')},ensure_ascii=True),flush=True)

if __name__=='__main__':asyncio.run(main())
