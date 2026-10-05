"""Run available reference assets, with at most three live Tripo jobs."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.generate_archipelago_prop import run, ProviderError, BASE
from tools.archipelago_queue import assert_authorized

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--assets',nargs='+',required=True)
    args=parser.parse_args()
    queue=json.loads((BASE/'queue.json').read_text(encoding='utf-8'))
    for asset in args.assets:
        assert_authorized(queue,asset)
    semaphore=asyncio.Semaphore(3)
    async def generate(asset):
        async with semaphore:
            try:
                item=next(item for item in queue['items'] if item['id']==asset)
                prompt_mode=item.get('generation_method')=='text'
                reference=BASE/asset/('tripo_prompt.txt' if prompt_mode else 'tripo_reference.png')
                while not reference.exists():
                    await asyncio.sleep(3)
                await run(SimpleNamespace(asset=asset, reference=reference,
                           prompt_file=reference if prompt_mode else None,
                           key_file=Path.home()/'Desktop/tripo_key.txt'))
                return {'asset':asset,'ok':True}
            except Exception as error:
                code=error.code if isinstance(error,ProviderError) else type(error).__name__
                print(json.dumps({'asset':asset,'error':code,'automatic_resubmit':False}),flush=True)
                return {'asset':asset,'ok':False,'error':code}
    results=await asyncio.gather(*(generate(asset) for asset in args.assets))
    print('BATCH_GENERATION_RESULTS',json.dumps(results),flush=True)
    if not all(result['ok'] for result in results):
        sys.exit(1)

if __name__=='__main__':
    asyncio.run(main())
