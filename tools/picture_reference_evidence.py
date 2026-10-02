"""Download outputs of already-recorded image tasks; never submit or print URLs."""
import asyncio,io,json,sqlite3,sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import Settings,read_tripo_key
from server.provider import TripoProvider,ProviderError
OUT=ROOT/'artifacts/picture-furniture-20261002'
async def main():
    provider=TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
    with sqlite3.connect((OUT/'server-data/world.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
        rows=conn.execute('SELECT parts FROM studio_jobs').fetchall()
    for row in rows:
        for part,entry in json.loads(row[0]).items():
            if not entry.get('image_task'):continue
            destination=OUT/'public'/('refined-'+part+'.png')
            if destination.exists():continue
            result=await provider.task(entry['image_task'])
            output=result.get('output',{})
            print(json.dumps({'part':part,'status':result.get('status'),'output_fields':list(output)}),flush=True)
            if result.get('status')!='success':continue
            url=output.get('generated_image_url') or output.get('image_url')
            if not isinstance(url,str):continue
            parsed=urlparse(url);host=parsed.hostname or ''
            if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or not (host.endswith('.tripo3d.ai') or host=='tripo-data.rg1.data.tripo3d.com'):raise ProviderError('unapproved_reference_host')
            blob=bytearray()
            async with httpx.AsyncClient(timeout=60,follow_redirects=False) as client:
                async with client.stream('GET',url) as reply:
                    if reply.status_code!=200:raise ProviderError('reference_download_failed')
                    async for chunk in reply.aiter_bytes():
                        blob.extend(chunk)
                        if len(blob)>20*1024*1024:raise ProviderError('reference_too_large')
            with Image.open(io.BytesIO(blob)) as image:
                image.verify()
            destination.write_bytes(blob)
            print(json.dumps({'part':part,'saved':destination.name,'bytes':len(blob)}))
if __name__=='__main__':
    try:asyncio.run(main())
    except ProviderError as error:print(json.dumps({'error':error.code}));sys.exit(1)
