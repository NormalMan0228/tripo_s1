"""Read-only operator check. Never prints secrets or raw upstream responses."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError

async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, help='Server-local UTF-8 secret file')
    args=parser.parse_args()
    try:
        settings=Settings(tripo_key=read_tripo_key(args.key_file)) if args.key_file else Settings()
    except ValueError as error:
        allowed={'invalid_tripo_key_file','configure_only_one_tripo_key_source'}
        code=str(error) if str(error) in allowed else 'invalid_server_configuration'
        print(json.dumps({'configured':False,'status':code}))
        return
    if not settings.tripo_key:
        print(json.dumps({'configured':False,'status':'key_not_configured'}))
        return
    try:
        balance=await TripoProvider(settings).balance()
        print(json.dumps({'configured':True,'status':'ok','available_credits':balance}))
    except ProviderError as error:
        print(json.dumps({'configured':True,'status':error.code}))

if __name__=='__main__': asyncio.run(main())
