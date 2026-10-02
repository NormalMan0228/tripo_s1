"""Portable, loopback-only demo server. Never loads Tripo credentials."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from server.app import create_app
from server.config import Settings

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',type=Path,default=Path(os.getenv('LOCALAPPDATA',str(Path.home()))) / 'TripothonDemo' / 'server-data')
    args=parser.parse_args()
    if not 1024<=args.port<=65535: parser.error('port must be 1024..65535')
    settings=Settings(data_dir=args.data_dir,mode='demo',tripo_key='',paid_enabled=False,
                      registration_code='',daily_generation_limit=100)
    app=create_app(settings)
    uvicorn.run(app,host='127.0.0.1',port=args.port,workers=1,access_log=False,
                proxy_headers=False,loop='asyncio',http='h11',ws='none')

if __name__=='__main__': main()
